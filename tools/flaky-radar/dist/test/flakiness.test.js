"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_test_1 = require("node:test");
const flakiness_1 = require("../src/analysis/flakiness");
const TEST_ID = "Cart › 총액을 계산한다";
function result(status, message) {
    return {
        id: TEST_ID,
        suite: "Cart",
        name: "총액을 계산한다",
        status,
        durationMs: 10,
        message,
    };
}
/** `statuses`를 순서대로 실행한 이력을 만든다. `commits`가 있으면 각 실행에 붙인다. */
function history(statuses, commits) {
    return {
        version: 1,
        runs: statuses.map((status, i) => ({
            runId: `run-${i}`,
            at: 1000 + i * 1000,
            commit: commits?.[i],
            results: [result(status)],
        })),
    };
}
const only = (h) => {
    const verdicts = (0, flakiness_1.analyze)(h);
    strict_1.default.equal(verdicts.length, 1, "판정이 하나 나와야 한다");
    return verdicts[0];
};
(0, node_test_1.describe)("같은 커밋 증거 — 가장 강한 신호", () => {
    (0, node_test_1.it)("코드가 같은데 결과가 갈리면 불안정으로 판정한다", () => {
        const v = only(history(["pass", "fail"], ["abc", "abc"]));
        strict_1.default.equal(v.flakiness, 1);
        strict_1.default.equal(v.contradictoryCommits, 1);
        strict_1.default.equal(v.comparableCommits, 1);
        strict_1.default.match(v.rationale, /코드가 그대로인데/);
    });
    (0, node_test_1.it)("코드가 같으면 결과도 같았던 경우는 불안정이 아니다", () => {
        // 커밋 abc에서 두 번 다 통과, 커밋 def에서 두 번 다 실패 = 회귀이지 플레이키가 아니다
        const v = only(history(["pass", "pass", "fail", "fail"], ["abc", "abc", "def", "def"]));
        strict_1.default.equal(v.flakiness, 0);
        strict_1.default.equal(v.contradictoryCommits, 0);
        strict_1.default.equal(v.comparableCommits, 2);
    });
    (0, node_test_1.it)("갈린 커밋과 안 갈린 커밋이 섞이면 비율로 낸다", () => {
        const v = only(history(["pass", "fail", "pass", "pass"], ["abc", "abc", "def", "def"]));
        strict_1.default.equal(v.comparableCommits, 2);
        strict_1.default.equal(v.contradictoryCommits, 1);
        strict_1.default.equal(v.flakiness, 0.5);
    });
    (0, node_test_1.it)("커밋마다 1회씩만 돌았으면 비교 근거가 없다", () => {
        const v = only(history(["pass", "fail", "pass"], ["a", "b", "c"]));
        strict_1.default.equal(v.comparableCommits, 0, "같은 커밋 반복 실행이 없으면 비교 불가");
        strict_1.default.match(v.rationale, /커밋 정보가 없어|전환/);
    });
    (0, node_test_1.it)("비교 가능한 커밋이 3개 이상이면 신뢰도가 높다", () => {
        const v = only(history(["pass", "fail", "pass", "fail", "pass", "fail"], ["a", "a", "b", "b", "c", "c"]));
        strict_1.default.equal(v.confidence, "high");
    });
});
(0, node_test_1.describe)("커밋 정보가 없을 때 — 회귀와 플레이키를 가른다", () => {
    (0, node_test_1.it)("통과가 쭉 이어지다 실패로 넘어간 건 회귀로 본다", () => {
        // 전환 1회. 진짜 버그가 들어온 모양이다.
        const v = only(history(["pass", "pass", "pass", "fail", "fail", "fail"]));
        strict_1.default.ok(v.flakiness <= 0.2, `회귀인데 불안정 점수가 높다: ${v.flakiness}`);
        strict_1.default.match(v.rationale, /회귀/);
    });
    (0, node_test_1.it)("결과가 계속 오가면 불안정으로 본다", () => {
        // 전환 5회. 코드가 아니라 테스트가 문제다.
        const v = only(history(["pass", "fail", "pass", "fail", "pass", "fail"]));
        strict_1.default.ok(v.flakiness >= 0.7, `플레이키인데 점수가 낮다: ${v.flakiness}`);
        strict_1.default.match(v.rationale, /계속 오갑니다/);
    });
    (0, node_test_1.it)("회귀보다 플레이키가 항상 높은 점수를 받는다", () => {
        const regression = only(history(["pass", "pass", "pass", "fail", "fail", "fail"]));
        const flaky = only(history(["pass", "fail", "pass", "fail", "pass", "fail"]));
        strict_1.default.ok(flaky.flakiness > regression.flakiness, "이 구분이 제품의 존재 이유다. 뒤집히면 안 된다");
    });
});
(0, node_test_1.describe)("불안정이 아닌 경우", () => {
    (0, node_test_1.it)("항상 통과하면 0점이다", () => {
        const v = only(history(["pass", "pass", "pass", "pass"]));
        strict_1.default.equal(v.flakiness, 0);
        strict_1.default.match(v.rationale, /모두 통과/);
    });
    (0, node_test_1.it)("항상 실패하면 불안정이 아니라 깨진 테스트라고 말한다", () => {
        const v = only(history(["fail", "fail", "fail"]));
        strict_1.default.equal(v.flakiness, 0);
        strict_1.default.match(v.rationale, /깨져 있는 테스트/);
    });
    (0, node_test_1.it)("같은 커밋에서 항상 실패해도 불안정이 아니다", () => {
        const v = only(history(["fail", "fail"], ["abc", "abc"]));
        strict_1.default.equal(v.flakiness, 0);
    });
});
(0, node_test_1.describe)("판정 대상 고르기", () => {
    (0, node_test_1.it)("skip은 통과도 실패도 아니므로 세지 않는다", () => {
        const v = only(history(["pass", "skip", "skip", "fail"], ["a", "a", "a", "a"]));
        strict_1.default.equal(v.totalRuns, 2, "skip 2건은 빠져야 한다");
        strict_1.default.equal(v.flakiness, 1);
    });
    (0, node_test_1.it)("실행 횟수가 모자라면 판정하지 않는다", () => {
        strict_1.default.equal((0, flakiness_1.analyze)(history(["pass"])).length, 0);
        strict_1.default.equal((0, flakiness_1.analyze)(history(["pass", "fail"]), { minRuns: 5 }).length, 0);
    });
    (0, node_test_1.it)("불안정한 순으로 정렬한다", () => {
        const stable = { id: "S › 안정", suite: "S", name: "안정" };
        const shaky = { id: "S › 불안정", suite: "S", name: "불안정" };
        const h = {
            version: 1,
            runs: [0, 1, 2, 3].map((i) => ({
                runId: `r${i}`,
                at: 1000 + i * 1000,
                commit: "same",
                results: [
                    { ...stable, status: "pass", durationMs: 1 },
                    { ...shaky, status: (i % 2 === 0 ? "pass" : "fail"), durationMs: 1 },
                ],
            })),
        };
        const verdicts = (0, flakiness_1.analyze)(h);
        strict_1.default.equal(verdicts[0]?.name, "불안정", "가장 불안정한 것이 맨 위여야 한다");
        strict_1.default.equal(verdicts[1]?.name, "안정");
    });
});
(0, node_test_1.describe)("판정 근거를 함께 낸다", () => {
    (0, node_test_1.it)("마지막 실패 메시지를 보여준다", () => {
        const h = {
            version: 1,
            runs: [
                { runId: "a", at: 1000, commit: "c", results: [result("fail", "타임아웃 5000ms")] },
                { runId: "b", at: 2000, commit: "c", results: [result("pass")] },
                { runId: "c", at: 3000, commit: "c", results: [result("fail", "커넥션 리셋")] },
            ],
        };
        const v = only(h);
        strict_1.default.equal(v.lastFailureMessage, "커넥션 리셋", "가장 최근 실패 이유를 보여야 한다");
        strict_1.default.equal(v.lastSeenAt, 3000);
    });
    (0, node_test_1.it)("모든 판정에 사람이 읽을 근거가 붙는다", () => {
        // 숫자만 던지면 아무도 믿지 않는다.
        for (const h of [
            history(["pass", "fail"], ["a", "a"]),
            history(["pass", "pass"]),
            history(["fail", "fail"]),
            history(["pass", "fail", "pass"]),
        ]) {
            strict_1.default.ok(only(h).rationale.length > 10, "근거 문장이 비어 있으면 안 된다");
        }
    });
    (0, node_test_1.it)("실패율을 그대로 보고한다", () => {
        const v = only(history(["pass", "fail", "fail", "fail"]));
        strict_1.default.equal(v.failures, 3);
        strict_1.default.equal(v.totalRuns, 4);
        strict_1.default.equal(v.failRate, 0.75);
    });
});
//# sourceMappingURL=flakiness.test.js.map