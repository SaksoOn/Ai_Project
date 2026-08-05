import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { LicenseGate, memoryStorage } from "../src/index";
import { DAY_MS, type Storage } from "../src/types";

const PRODUCT_ID = "prod_test";
const KEY = "AAAA-BBBB-CCCC-DDDD";

/** 호출을 세는 가짜 fetch. 재검증이 실제로 건너뛰어지는지 확인하는 데 쓴다. */
function fakeFetch(handler: () => Promise<Response> | Response) {
  const fn = (async () => {
    fn.calls += 1;
    return await handler();
  }) as unknown as typeof globalThis.fetch & { calls: number };
  fn.calls = 0;
  return fn;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
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
    advance: (ms: number) => {
      t += ms;
    },
    rewind: (ms: number) => {
      t -= ms;
    },
  };
}

function gate(
  storage: Storage,
  now: () => number,
  fetchImpl: typeof globalThis.fetch,
  config: { trialDays?: number; reverifyAfterDays?: number; offlineGraceDays?: number } = {},
) {
  return new LicenseGate({ productId: PRODUCT_ID, ...config }, storage, { now, fetch: fetchImpl });
}

describe("체험 기간", () => {
  let store: Storage;
  let time: ReturnType<typeof clock>;

  beforeEach(() => {
    store = memoryStorage();
    time = clock();
  });

  it("첫 실행에 체험이 시작되고 7일이 남는다", async () => {
    const g = gate(store, time.now, fakeFetch(ok));
    const e = await g.check();
    assert.equal(e.status, "trial");
    assert.equal(e.status === "trial" && e.daysRemaining, 7);
  });

  it("체험 중에는 네트워크를 전혀 쓰지 않는다", async () => {
    const f = fakeFetch(ok);
    await gate(store, time.now, f).check();
    time.advance(3 * DAY_MS);
    await gate(store, time.now, f).check();
    assert.equal(f.calls, 0, "체험 상태에서 Gumroad를 호출하면 안 된다");
  });

  it("마지막 날에도 여전히 쓸 수 있다", async () => {
    const g = gate(store, time.now, fakeFetch(ok));
    await g.check();
    time.advance(7 * DAY_MS - 1000);
    const e = await gate(store, time.now, fakeFetch(ok)).check();
    assert.equal(e.status, "trial");
  });

  it("7일이 지나면 잠긴다", async () => {
    await gate(store, time.now, fakeFetch(ok)).check();
    time.advance(7 * DAY_MS);
    const e = await gate(store, time.now, fakeFetch(ok)).check();
    assert.equal(e.status, "expired");
    assert.equal(e.status === "expired" && e.reason, "trial-ended");
  });

  it("시계를 되돌려도 체험이 늘어나지 않는다", async () => {
    await gate(store, time.now, fakeFetch(ok)).check();
    time.advance(8 * DAY_MS);
    assert.equal((await gate(store, time.now, fakeFetch(ok)).check()).status, "expired");

    time.rewind(30 * DAY_MS); // 시계를 한 달 뒤로 돌린다
    const e = await gate(store, time.now, fakeFetch(ok)).check();
    assert.equal(e.status, "expired", "시계 되돌리기로 체험이 부활하면 안 된다");
  });
});

describe("라이선스 활성화", () => {
  let store: Storage;
  let time: ReturnType<typeof clock>;

  beforeEach(() => {
    store = memoryStorage();
    time = clock();
  });

  it("유효한 키로 잠금이 풀린다", async () => {
    const g = gate(store, time.now, fakeFetch(ok));
    const result = await g.activate(KEY);
    assert.equal(result.ok, true);
    const e = await g.check();
    assert.equal(e.status, "licensed");
    assert.equal(e.status === "licensed" && e.stale, false);
  });

  it("체험이 끝난 뒤에도 활성화하면 바로 풀린다", async () => {
    await gate(store, time.now, fakeFetch(ok)).check();
    time.advance(10 * DAY_MS);
    assert.equal((await gate(store, time.now, fakeFetch(ok)).check()).status, "expired");

    const g = gate(store, time.now, fakeFetch(ok));
    assert.equal((await g.activate(KEY)).ok, true);
    assert.equal((await g.check()).status, "licensed");
  });

  it("없는 키는 거부한다", async () => {
    const f = fakeFetch(() => json({ success: false, message: "not found" }, 404));
    const result = await gate(store, time.now, f).activate(KEY);
    assert.equal(result.ok, false);
    assert.equal(result.ok === false && result.reason, "invalid-key");
  });

  it("빈 키는 네트워크를 쓰지 않고 거부한다", async () => {
    const f = fakeFetch(ok);
    const result = await gate(store, time.now, f).activate("   ");
    assert.equal(result.ok, false);
    assert.equal(f.calls, 0);
  });

  it("오프라인에서는 활성화를 보류하되 키를 저장하지 않는다", async () => {
    const g = gate(store, time.now, fakeFetch(offline));
    const result = await g.activate(KEY);
    assert.equal(result.ok, false);
    assert.equal(result.ok === false && result.reason, "offline");
    // 검증 없이 키가 저장되면 아무 문자열로나 잠금이 풀린다.
    assert.notEqual((await gate(store, time.now, fakeFetch(offline)).check()).status, "licensed");
  });
});

describe("오프라인 유예 — 유료 사용자를 네트워크 때문에 잠그지 않는다", () => {
  let store: Storage;
  let time: ReturnType<typeof clock>;

  beforeEach(async () => {
    store = memoryStorage();
    time = clock();
    await gate(store, time.now, fakeFetch(ok)).activate(KEY);
  });

  it("재검증 주기 안에는 네트워크를 아예 안 쓴다", async () => {
    const f = fakeFetch(offline);
    time.advance(6 * DAY_MS);
    const e = await gate(store, time.now, f).check();
    assert.equal(e.status, "licensed");
    assert.equal(f.calls, 0, "주기 내에는 호출하면 안 된다");
  });

  it("주기가 지나고 연결이 안 되면 stale 상태로 계속 쓴다", async () => {
    time.advance(10 * DAY_MS); // 재검증(7일)은 지났고 유예(14일)는 남음
    const e = await gate(store, time.now, fakeFetch(offline)).check();
    assert.equal(e.status, "licensed", "비행기에서 잠기면 안 된다");
    assert.equal(e.status === "licensed" && e.stale, true);
  });

  it("Gumroad 장애(5xx)도 연결 실패로 취급한다", async () => {
    time.advance(10 * DAY_MS);
    const f = fakeFetch(() => json({ error: "boom" }, 503));
    const e = await gate(store, time.now, f).check();
    assert.equal(e.status, "licensed", "판매자 서버 장애로 구매자가 잠기면 안 된다");
  });

  it("유예까지 지나면 그때는 잠근다", async () => {
    time.advance(22 * DAY_MS); // 재검증 7일 + 유예 14일 초과
    const e = await gate(store, time.now, fakeFetch(offline)).check();
    assert.equal(e.status, "revoked");
    assert.equal(e.status === "revoked" && e.reason, "offline-grace-expired");
  });

  it("연결이 돌아오면 다시 정상 상태가 된다", async () => {
    time.advance(10 * DAY_MS);
    assert.equal(
      (await gate(store, time.now, fakeFetch(offline)).check()).status === "licensed",
      true,
    );
    const e = await gate(store, time.now, fakeFetch(ok)).check();
    assert.equal(e.status === "licensed" && e.stale, false);
  });
});

describe("구매 무효화", () => {
  let store: Storage;
  let time: ReturnType<typeof clock>;

  beforeEach(async () => {
    store = memoryStorage();
    time = clock();
    await gate(store, time.now, fakeFetch(ok)).activate(KEY);
    time.advance(8 * DAY_MS); // 재검증이 일어나도록
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
  ] as const;

  for (const [label, body, expected] of revokes) {
    it(`${label} 시 잠근다`, async () => {
      const e = await gate(store, time.now, fakeFetch(() => json(body))).check();
      assert.equal(e.status, "revoked");
      assert.equal(e.status === "revoked" && e.reason, expected);
    });
  }

  it("무효화 이후에는 네트워크를 다시 쓰지 않는다", async () => {
    await gate(store, time.now, fakeFetch(() => json({ success: true, purchase: { refunded: true } }))).check();
    const f = fakeFetch(ok);
    const e = await gate(store, time.now, f).check();
    assert.equal(e.status, "revoked");
    assert.equal(f.calls, 0);
  });

  it("null 구독 필드는 정상으로 본다", async () => {
    const body = {
      success: true,
      purchase: { subscription_cancelled_at: null, subscription_ended_at: null, refunded: false },
    };
    const e = await gate(store, time.now, fakeFetch(() => json(body))).check();
    assert.equal(e.status, "licensed");
  });

  it("purchase 필드가 통째로 없어도 잠그지 않는다", async () => {
    // Gumroad가 응답 형태를 바꿔도 유료 사용자가 갑자기 잠기면 안 된다.
    const e = await gate(store, time.now, fakeFetch(() => json({ success: true }))).check();
    assert.equal(e.status, "licensed");
  });
});

describe("해제", () => {
  it("라이선스를 풀어도 이미 쓴 체험이 되살아나지 않는다", async () => {
    const store = memoryStorage();
    const time = clock();
    await gate(store, time.now, fakeFetch(ok)).check(); // 체험 시작
    time.advance(9 * DAY_MS); // 체험 소진
    await gate(store, time.now, fakeFetch(ok)).activate(KEY);

    const g = gate(store, time.now, fakeFetch(ok));
    await g.deactivate();
    const e = await g.check();
    assert.equal(e.status, "expired", "해제로 체험이 부활하면 안 된다");
  });
});
