"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_test_1 = require("node:test");
const history_1 = require("../src/store/history");
const types_1 = require("../src/types");
function run(runId, at) {
    return {
        runId,
        at,
        commit: "abc",
        results: [{ id: "S › t", suite: "S", name: "t", status: "pass", durationMs: 1 }],
    };
}
(0, node_test_1.describe)("이력 누적", () => {
    (0, node_test_1.it)("실행을 더한다", () => {
        const h = (0, history_1.appendRun)(types_1.EMPTY_HISTORY, run("a", 1000));
        strict_1.default.equal(h.runs.length, 1);
    });
    (0, node_test_1.it)("같은 runId는 중복 집계하지 않는다", () => {
        // 파일 감시자는 저장 한 번에 이벤트를 여러 번 쏜다. 그대로 받으면 판정이 틀어진다.
        let h = (0, history_1.appendRun)(types_1.EMPTY_HISTORY, run("a", 1000));
        h = (0, history_1.appendRun)(h, run("a", 1000));
        h = (0, history_1.appendRun)(h, run("a", 1000));
        strict_1.default.equal(h.runs.length, 1, "중복 이벤트가 이력을 부풀리면 안 된다");
    });
    (0, node_test_1.it)("시간순으로 정렬한다", () => {
        let h = (0, history_1.appendRun)(types_1.EMPTY_HISTORY, run("late", 3000));
        h = (0, history_1.appendRun)(h, run("early", 1000));
        strict_1.default.deepEqual(h.runs.map((r) => r.runId), ["early", "late"]);
    });
    (0, node_test_1.it)("상한을 넘으면 오래된 것부터 버린다", () => {
        let h = types_1.EMPTY_HISTORY;
        for (let i = 0; i < 10; i += 1)
            h = (0, history_1.appendRun)(h, run(`r${i}`, 1000 + i), 3);
        strict_1.default.equal(h.runs.length, 3);
        strict_1.default.deepEqual(h.runs.map((r) => r.runId), ["r7", "r8", "r9"]);
    });
});
(0, node_test_1.describe)("이력 읽기 — 손상돼도 확장이 죽지 않아야 한다", () => {
    (0, node_test_1.it)("정상 JSON을 읽는다", () => {
        const h = (0, history_1.appendRun)(types_1.EMPTY_HISTORY, run("a", 1000));
        strict_1.default.deepEqual((0, history_1.parseHistory)((0, history_1.serializeHistory)(h)), h);
    });
    (0, node_test_1.it)("빈 값은 빈 이력이다", () => {
        strict_1.default.deepEqual((0, history_1.parseHistory)(undefined), types_1.EMPTY_HISTORY);
        strict_1.default.deepEqual((0, history_1.parseHistory)(""), types_1.EMPTY_HISTORY);
    });
    (0, node_test_1.it)("깨진 JSON은 빈 이력으로 시작한다", () => {
        // 이력을 잃는 것이 확장이 안 켜지는 것보다 낫다.
        strict_1.default.deepEqual((0, history_1.parseHistory)("{망가진"), types_1.EMPTY_HISTORY);
    });
    (0, node_test_1.it)("모르는 버전은 버린다", () => {
        strict_1.default.deepEqual((0, history_1.parseHistory)('{"version":99,"runs":[]}'), types_1.EMPTY_HISTORY);
    });
    (0, node_test_1.it)("형태가 이상한 run은 걸러낸다", () => {
        const raw = '{"version":1,"runs":[{"runId":"ok","at":1,"results":[]},{"쓰레기":true},null]}';
        strict_1.default.equal((0, history_1.parseHistory)(raw).runs.length, 1);
    });
});
(0, node_test_1.describe)("HistoryStore", () => {
    (0, node_test_1.it)("불러오기·더하기·비우기가 파일에 반영된다", async () => {
        const io = (0, history_1.memoryIO)();
        const store = new history_1.HistoryStore(io);
        strict_1.default.deepEqual(await store.load(), types_1.EMPTY_HISTORY);
        await store.append(run("a", 1000));
        await store.append(run("b", 2000));
        strict_1.default.equal((await store.load()).runs.length, 2);
        await store.append(run("b", 2000));
        strict_1.default.equal((await store.load()).runs.length, 2, "중복은 저장 후에도 걸러져야 한다");
        await store.clear();
        strict_1.default.equal((await store.load()).runs.length, 0);
    });
});
//# sourceMappingURL=history.test.js.map