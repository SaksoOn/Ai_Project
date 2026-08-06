"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_test_1 = require("node:test");
const index_1 = require("../src/index");
const types_1 = require("../src/types");
const PRODUCT_ID = "prod_test";
const KEY = "AAAA-BBBB-CCCC-DDDD";
/** 호출을 세는 가짜 fetch. 재검증이 실제로 건너뛰어지는지 확인하는 데 쓴다. */
function fakeFetch(handler) {
    const fn = (async () => {
        fn.calls += 1;
        return await handler();
    });
    fn.calls = 0;
    return fn;
}
const json = (body, status = 200) => new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
});
const ok = () => json({ success: true, uses: 1, purchase: {} });
const offline = () => {
    throw new Error("getaddrinfo ENOTFOUND api.gumroad.com");
};
/** 시각을 마음대로 옮길 수 있는 클럭. */
function clock(start = 1_700_000_000_000) {
    let t = start;
    return {
        now: () => t,
        advance: (ms) => {
            t += ms;
        },
        rewind: (ms) => {
            t -= ms;
        },
    };
}
function gate(storage, now, fetchImpl, config = {}) {
    return new index_1.LicenseGate({ productId: PRODUCT_ID, ...config }, storage, { now, fetch: fetchImpl });
}
(0, node_test_1.describe)("체험 기간", () => {
    let store;
    let time;
    (0, node_test_1.beforeEach)(() => {
        store = (0, index_1.memoryStorage)();
        time = clock();
    });
    (0, node_test_1.it)("첫 실행에 체험이 시작되고 7일이 남는다", async () => {
        const g = gate(store, time.now, fakeFetch(ok));
        const e = await g.check();
        strict_1.default.equal(e.status, "trial");
        strict_1.default.equal(e.status === "trial" && e.daysRemaining, 7);
    });
    (0, node_test_1.it)("체험 중에는 네트워크를 전혀 쓰지 않는다", async () => {
        const f = fakeFetch(ok);
        await gate(store, time.now, f).check();
        time.advance(3 * types_1.DAY_MS);
        await gate(store, time.now, f).check();
        strict_1.default.equal(f.calls, 0, "체험 상태에서 Gumroad를 호출하면 안 된다");
    });
    (0, node_test_1.it)("마지막 날에도 여전히 쓸 수 있다", async () => {
        const g = gate(store, time.now, fakeFetch(ok));
        await g.check();
        time.advance(7 * types_1.DAY_MS - 1000);
        const e = await gate(store, time.now, fakeFetch(ok)).check();
        strict_1.default.equal(e.status, "trial");
    });
    (0, node_test_1.it)("7일이 지나면 잠긴다", async () => {
        await gate(store, time.now, fakeFetch(ok)).check();
        time.advance(7 * types_1.DAY_MS);
        const e = await gate(store, time.now, fakeFetch(ok)).check();
        strict_1.default.equal(e.status, "expired");
        strict_1.default.equal(e.status === "expired" && e.reason, "trial-ended");
    });
    (0, node_test_1.it)("시계를 되돌려도 체험이 늘어나지 않는다", async () => {
        await gate(store, time.now, fakeFetch(ok)).check();
        time.advance(8 * types_1.DAY_MS);
        strict_1.default.equal((await gate(store, time.now, fakeFetch(ok)).check()).status, "expired");
        time.rewind(30 * types_1.DAY_MS); // 시계를 한 달 뒤로 돌린다
        const e = await gate(store, time.now, fakeFetch(ok)).check();
        strict_1.default.equal(e.status, "expired", "시계 되돌리기로 체험이 부활하면 안 된다");
    });
});
(0, node_test_1.describe)("라이선스 활성화", () => {
    let store;
    let time;
    (0, node_test_1.beforeEach)(() => {
        store = (0, index_1.memoryStorage)();
        time = clock();
    });
    (0, node_test_1.it)("유효한 키로 잠금이 풀린다", async () => {
        const g = gate(store, time.now, fakeFetch(ok));
        const result = await g.activate(KEY);
        strict_1.default.equal(result.ok, true);
        const e = await g.check();
        strict_1.default.equal(e.status, "licensed");
        strict_1.default.equal(e.status === "licensed" && e.stale, false);
    });
    (0, node_test_1.it)("체험이 끝난 뒤에도 활성화하면 바로 풀린다", async () => {
        await gate(store, time.now, fakeFetch(ok)).check();
        time.advance(10 * types_1.DAY_MS);
        strict_1.default.equal((await gate(store, time.now, fakeFetch(ok)).check()).status, "expired");
        const g = gate(store, time.now, fakeFetch(ok));
        strict_1.default.equal((await g.activate(KEY)).ok, true);
        strict_1.default.equal((await g.check()).status, "licensed");
    });
    (0, node_test_1.it)("없는 키는 거부한다", async () => {
        const f = fakeFetch(() => json({ success: false, message: "not found" }, 404));
        const result = await gate(store, time.now, f).activate(KEY);
        strict_1.default.equal(result.ok, false);
        strict_1.default.equal(result.ok === false && result.reason, "invalid-key");
    });
    (0, node_test_1.it)("빈 키는 네트워크를 쓰지 않고 거부한다", async () => {
        const f = fakeFetch(ok);
        const result = await gate(store, time.now, f).activate("   ");
        strict_1.default.equal(result.ok, false);
        strict_1.default.equal(f.calls, 0);
    });
    (0, node_test_1.it)("오프라인에서는 활성화를 보류하되 키를 저장하지 않는다", async () => {
        const g = gate(store, time.now, fakeFetch(offline));
        const result = await g.activate(KEY);
        strict_1.default.equal(result.ok, false);
        strict_1.default.equal(result.ok === false && result.reason, "offline");
        // 검증 없이 키가 저장되면 아무 문자열로나 잠금이 풀린다.
        strict_1.default.notEqual((await gate(store, time.now, fakeFetch(offline)).check()).status, "licensed");
    });
});
(0, node_test_1.describe)("오프라인 유예 — 유료 사용자를 네트워크 때문에 잠그지 않는다", () => {
    let store;
    let time;
    (0, node_test_1.beforeEach)(async () => {
        store = (0, index_1.memoryStorage)();
        time = clock();
        await gate(store, time.now, fakeFetch(ok)).activate(KEY);
    });
    (0, node_test_1.it)("재검증 주기 안에는 네트워크를 아예 안 쓴다", async () => {
        const f = fakeFetch(offline);
        time.advance(6 * types_1.DAY_MS);
        const e = await gate(store, time.now, f).check();
        strict_1.default.equal(e.status, "licensed");
        strict_1.default.equal(f.calls, 0, "주기 내에는 호출하면 안 된다");
    });
    (0, node_test_1.it)("주기가 지나고 연결이 안 되면 stale 상태로 계속 쓴다", async () => {
        time.advance(10 * types_1.DAY_MS); // 재검증(7일)은 지났고 유예(14일)는 남음
        const e = await gate(store, time.now, fakeFetch(offline)).check();
        strict_1.default.equal(e.status, "licensed", "비행기에서 잠기면 안 된다");
        strict_1.default.equal(e.status === "licensed" && e.stale, true);
    });
    (0, node_test_1.it)("Gumroad 장애(5xx)도 연결 실패로 취급한다", async () => {
        time.advance(10 * types_1.DAY_MS);
        const f = fakeFetch(() => json({ error: "boom" }, 503));
        const e = await gate(store, time.now, f).check();
        strict_1.default.equal(e.status, "licensed", "판매자 서버 장애로 구매자가 잠기면 안 된다");
    });
    (0, node_test_1.it)("유예까지 지나면 그때는 잠근다", async () => {
        time.advance(22 * types_1.DAY_MS); // 재검증 7일 + 유예 14일 초과
        const e = await gate(store, time.now, fakeFetch(offline)).check();
        strict_1.default.equal(e.status, "revoked");
        strict_1.default.equal(e.status === "revoked" && e.reason, "offline-grace-expired");
    });
    (0, node_test_1.it)("연결이 돌아오면 다시 정상 상태가 된다", async () => {
        time.advance(10 * types_1.DAY_MS);
        strict_1.default.equal((await gate(store, time.now, fakeFetch(offline)).check()).status === "licensed", true);
        const e = await gate(store, time.now, fakeFetch(ok)).check();
        strict_1.default.equal(e.status === "licensed" && e.stale, false);
    });
});
(0, node_test_1.describe)("구매 무효화", () => {
    let store;
    let time;
    (0, node_test_1.beforeEach)(async () => {
        store = (0, index_1.memoryStorage)();
        time = clock();
        await gate(store, time.now, fakeFetch(ok)).activate(KEY);
        time.advance(8 * types_1.DAY_MS); // 재검증이 일어나도록
    });
    const revokes = [
        ["환불", { success: true, purchase: { refunded: true } }, "refunded"],
        ["분쟁", { success: true, purchase: { disputed: true } }, "disputed"],
        ["차지백", { success: true, purchase: { chargebacked: true } }, "disputed"],
        [
            "구독 취소",
            { success: true, purchase: { subscription_cancelled_at: "2026-01-01T00:00:00Z" } },
            "subscription-ended",
        ],
        [
            "구독 결제 실패",
            { success: true, purchase: { subscription_failed_at: "2026-01-01T00:00:00Z" } },
            "subscription-ended",
        ],
    ];
    for (const [label, body, expected] of revokes) {
        (0, node_test_1.it)(`${label} 시 잠근다`, async () => {
            const e = await gate(store, time.now, fakeFetch(() => json(body))).check();
            strict_1.default.equal(e.status, "revoked");
            strict_1.default.equal(e.status === "revoked" && e.reason, expected);
        });
    }
    (0, node_test_1.it)("무효화 이후에는 네트워크를 다시 쓰지 않는다", async () => {
        await gate(store, time.now, fakeFetch(() => json({ success: true, purchase: { refunded: true } }))).check();
        const f = fakeFetch(ok);
        const e = await gate(store, time.now, f).check();
        strict_1.default.equal(e.status, "revoked");
        strict_1.default.equal(f.calls, 0);
    });
    (0, node_test_1.it)("null 구독 필드는 정상으로 본다", async () => {
        const body = {
            success: true,
            purchase: { subscription_cancelled_at: null, subscription_ended_at: null, refunded: false },
        };
        const e = await gate(store, time.now, fakeFetch(() => json(body))).check();
        strict_1.default.equal(e.status, "licensed");
    });
    (0, node_test_1.it)("purchase 필드가 통째로 없어도 잠그지 않는다", async () => {
        // Gumroad가 응답 형태를 바꿔도 유료 사용자가 갑자기 잠기면 안 된다.
        const e = await gate(store, time.now, fakeFetch(() => json({ success: true }))).check();
        strict_1.default.equal(e.status, "licensed");
    });
});
(0, node_test_1.describe)("해제", () => {
    (0, node_test_1.it)("라이선스를 풀어도 이미 쓴 체험이 되살아나지 않는다", async () => {
        const store = (0, index_1.memoryStorage)();
        const time = clock();
        await gate(store, time.now, fakeFetch(ok)).check(); // 체험 시작
        time.advance(9 * types_1.DAY_MS); // 체험 소진
        await gate(store, time.now, fakeFetch(ok)).activate(KEY);
        const g = gate(store, time.now, fakeFetch(ok));
        await g.deactivate();
        const e = await g.check();
        strict_1.default.equal(e.status, "expired", "해제로 체험이 부활하면 안 된다");
    });
});
//# sourceMappingURL=gate.test.js.map