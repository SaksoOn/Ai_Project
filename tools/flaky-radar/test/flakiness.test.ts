import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { analyze } from "../src/analysis/flakiness";
import type { History, TestResult, TestStatus } from "../src/types";

const TEST_ID = "Cart › 총액을 계산한다";

function result(status: TestStatus, message?: string): TestResult {
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
function history(statuses: TestStatus[], commits?: (string | undefined)[]): History {
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

const only = (h: History) => {
  const verdicts = analyze(h);
  assert.equal(verdicts.length, 1, "판정이 하나 나와야 한다");
  return verdicts[0]!;
};

describe("같은 커밋 증거 — 가장 강한 신호", () => {
  it("코드가 같은데 결과가 갈리면 불안정으로 판정한다", () => {
    const v = only(history(["pass", "fail"], ["abc", "abc"]));
    assert.equal(v.flakiness, 1);
    assert.equal(v.contradictoryCommits, 1);
    assert.equal(v.comparableCommits, 1);
    assert.match(v.rationale, /코드가 그대로인데/);
  });

  it("코드가 같으면 결과도 같았던 경우는 불안정이 아니다", () => {
    // 커밋 abc에서 두 번 다 통과, 커밋 def에서 두 번 다 실패 = 회귀이지 플레이키가 아니다
    const v = only(history(["pass", "pass", "fail", "fail"], ["abc", "abc", "def", "def"]));
    assert.equal(v.flakiness, 0);
    assert.equal(v.contradictoryCommits, 0);
    assert.equal(v.comparableCommits, 2);
  });

  it("갈린 커밋과 안 갈린 커밋이 섞이면 비율로 낸다", () => {
    const v = only(
      history(
        ["pass", "fail", "pass", "pass"],
        ["abc", "abc", "def", "def"],
      ),
    );
    assert.equal(v.comparableCommits, 2);
    assert.equal(v.contradictoryCommits, 1);
    assert.equal(v.flakiness, 0.5);
  });

  it("커밋마다 1회씩만 돌았으면 비교 근거가 없다", () => {
    const v = only(history(["pass", "fail", "pass"], ["a", "b", "c"]));
    assert.equal(v.comparableCommits, 0, "같은 커밋 반복 실행이 없으면 비교 불가");
    assert.match(v.rationale, /커밋 정보가 없어|전환/);
  });

  it("비교 가능한 커밋이 3개 이상이면 신뢰도가 높다", () => {
    const v = only(
      history(
        ["pass", "fail", "pass", "fail", "pass", "fail"],
        ["a", "a", "b", "b", "c", "c"],
      ),
    );
    assert.equal(v.confidence, "high");
  });
});

describe("커밋 정보가 없을 때 — 회귀와 플레이키를 가른다", () => {
  it("통과가 쭉 이어지다 실패로 넘어간 건 회귀로 본다", () => {
    // 전환 1회. 진짜 버그가 들어온 모양이다.
    const v = only(history(["pass", "pass", "pass", "fail", "fail", "fail"]));
    assert.ok(v.flakiness <= 0.2, `회귀인데 불안정 점수가 높다: ${v.flakiness}`);
    assert.match(v.rationale, /회귀/);
  });

  it("결과가 계속 오가면 불안정으로 본다", () => {
    // 전환 5회. 코드가 아니라 테스트가 문제다.
    const v = only(history(["pass", "fail", "pass", "fail", "pass", "fail"]));
    assert.ok(v.flakiness >= 0.7, `플레이키인데 점수가 낮다: ${v.flakiness}`);
    assert.match(v.rationale, /계속 오갑니다/);
  });

  it("회귀보다 플레이키가 항상 높은 점수를 받는다", () => {
    const regression = only(history(["pass", "pass", "pass", "fail", "fail", "fail"]));
    const flaky = only(history(["pass", "fail", "pass", "fail", "pass", "fail"]));
    assert.ok(
      flaky.flakiness > regression.flakiness,
      "이 구분이 제품의 존재 이유다. 뒤집히면 안 된다",
    );
  });
});

describe("불안정이 아닌 경우", () => {
  it("항상 통과하면 0점이다", () => {
    const v = only(history(["pass", "pass", "pass", "pass"]));
    assert.equal(v.flakiness, 0);
    assert.match(v.rationale, /모두 통과/);
  });

  it("항상 실패하면 불안정이 아니라 깨진 테스트라고 말한다", () => {
    const v = only(history(["fail", "fail", "fail"]));
    assert.equal(v.flakiness, 0);
    assert.match(v.rationale, /깨져 있는 테스트/);
  });

  it("같은 커밋에서 항상 실패해도 불안정이 아니다", () => {
    const v = only(history(["fail", "fail"], ["abc", "abc"]));
    assert.equal(v.flakiness, 0);
  });
});

describe("판정 대상 고르기", () => {
  it("skip은 통과도 실패도 아니므로 세지 않는다", () => {
    const v = only(history(["pass", "skip", "skip", "fail"], ["a", "a", "a", "a"]));
    assert.equal(v.totalRuns, 2, "skip 2건은 빠져야 한다");
    assert.equal(v.flakiness, 1);
  });

  it("실행 횟수가 모자라면 판정하지 않는다", () => {
    assert.equal(analyze(history(["pass"])).length, 0);
    assert.equal(analyze(history(["pass", "fail"]), { minRuns: 5 }).length, 0);
  });

  it("불안정한 순으로 정렬한다", () => {
    const stable = { id: "S › 안정", suite: "S", name: "안정" };
    const shaky = { id: "S › 불안정", suite: "S", name: "불안정" };
    const h: History = {
      version: 1,
      runs: [0, 1, 2, 3].map((i) => ({
        runId: `r${i}`,
        at: 1000 + i * 1000,
        commit: "same",
        results: [
          { ...stable, status: "pass" as TestStatus, durationMs: 1 },
          { ...shaky, status: (i % 2 === 0 ? "pass" : "fail") as TestStatus, durationMs: 1 },
        ],
      })),
    };
    const verdicts = analyze(h);
    assert.equal(verdicts[0]?.name, "불안정", "가장 불안정한 것이 맨 위여야 한다");
    assert.equal(verdicts[1]?.name, "안정");
  });
});

describe("판정 근거를 함께 낸다", () => {
  it("마지막 실패 메시지를 보여준다", () => {
    const h: History = {
      version: 1,
      runs: [
        { runId: "a", at: 1000, commit: "c", results: [result("fail", "타임아웃 5000ms")] },
        { runId: "b", at: 2000, commit: "c", results: [result("pass")] },
        { runId: "c", at: 3000, commit: "c", results: [result("fail", "커넥션 리셋")] },
      ],
    };
    const v = only(h);
    assert.equal(v.lastFailureMessage, "커넥션 리셋", "가장 최근 실패 이유를 보여야 한다");
    assert.equal(v.lastSeenAt, 3000);
  });

  it("모든 판정에 사람이 읽을 근거가 붙는다", () => {
    // 숫자만 던지면 아무도 믿지 않는다.
    for (const h of [
      history(["pass", "fail"], ["a", "a"]),
      history(["pass", "pass"]),
      history(["fail", "fail"]),
      history(["pass", "fail", "pass"]),
    ]) {
      assert.ok(only(h).rationale.length > 10, "근거 문장이 비어 있으면 안 된다");
    }
  });

  it("실패율을 그대로 보고한다", () => {
    const v = only(history(["pass", "fail", "fail", "fail"]));
    assert.equal(v.failures, 3);
    assert.equal(v.totalRuns, 4);
    assert.equal(v.failRate, 0.75);
  });
});
