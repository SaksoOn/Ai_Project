import type { Confidence, FlakyVerdict, History, TestResult, TestRun } from "../types";

interface Observation {
  at: number;
  commit: string | undefined;
  result: TestResult;
}

export interface AnalyzeOptions {
  /** 이 횟수 미만으로 실행된 테스트는 판정하지 않는다. 기본 2. */
  minRuns?: number;
}

/**
 * 커밋 정보가 없을 때 쓰는 보조 신호의 할인율.
 *
 * 전환 횟수는 꽤 좋은 신호지만 확정적이지는 않다. 같은 커밋에서 결과가 갈린 것만이
 * 코드 변경 가능성을 배제한 증거다.
 */
const TRANSITION_DISCOUNT = 0.8;

/**
 * 실행 이력에서 불안정한 테스트를 찾아낸다.
 *
 * 판정 근거는 두 가지이고, 강한 쪽을 우선한다.
 *
 * 1. **같은 커밋에서 결과가 갈렸는가** — 코드가 그대로인데 결과가 다르면 테스트가 문제다.
 *    이게 확정적 증거다.
 * 2. **통과와 실패가 번갈아 나타나는가** — 커밋 정보가 없을 때 쓴다.
 *    진짜 회귀는 통과가 쭉 이어지다 실패로 한 번 넘어가지만(전환 1회),
 *    불안정한 테스트는 계속 오간다. 이 차이로 회귀와 플레이키를 구분한다.
 */
export function analyze(history: History, options: AnalyzeOptions = {}): FlakyVerdict[] {
  const minRuns = options.minRuns ?? 2;
  const byTest = collect(history.runs);
  const verdicts: FlakyVerdict[] = [];

  for (const [id, observations] of byTest) {
    // 건너뛴 실행은 통과도 실패도 아니므로 판정에서 제외한다.
    const graded = observations
      .filter((o) => o.result.status !== "skip")
      .sort((a, b) => a.at - b.at);

    if (graded.length < minRuns) continue;

    const first = graded[0];
    const last = graded[graded.length - 1];
    if (!first || !last) continue;

    const totalRuns = graded.length;
    const failures = graded.filter((o) => o.result.status === "fail").length;
    const failRate = failures / totalRuns;

    const { contradictoryCommits, comparableCommits } = commitEvidence(graded);
    const transitions = countTransitions(graded);

    let flakiness: number;
    let rationale: string;

    if (comparableCommits > 0) {
      flakiness = contradictoryCommits / comparableCommits;
      rationale =
        `같은 커밋에서 결과가 갈린 적 ${contradictoryCommits}/${comparableCommits}회. ` +
        (contradictoryCommits > 0
          ? "코드가 그대로인데 결과가 달랐습니다 — 테스트 자체가 불안정합니다."
          : "코드가 같으면 결과도 항상 같았습니다.");
    } else if (totalRuns >= 3) {
      flakiness = (transitions / (totalRuns - 1)) * TRANSITION_DISCOUNT;
      rationale =
        `커밋 정보가 없어 전환 횟수로 추정했습니다. ` +
        `${totalRuns}회 실행 중 통과↔실패 전환 ${transitions}회. ` +
        (transitions <= 1
          ? "전환이 거의 없어 회귀(진짜 버그)일 가능성이 높습니다."
          : "결과가 계속 오갑니다 — 불안정한 테스트로 보입니다.");
    } else {
      flakiness = 0;
      rationale = `실행 ${totalRuns}회로는 판단하기 이릅니다.`;
    }

    // 항상 통과하거나 항상 실패하면 불안정한 게 아니다.
    // 전자는 정상이고 후자는 그냥 깨진 테스트다.
    if (failures === 0 || failures === totalRuns) {
      flakiness = 0;
      rationale =
        failures === 0
          ? `${totalRuns}회 모두 통과했습니다.`
          : `${totalRuns}회 모두 실패했습니다. 불안정한 게 아니라 깨져 있는 테스트입니다.`;
    }

    const lastFailure = [...graded].reverse().find((o) => o.result.status === "fail");

    verdicts.push({
      id,
      suite: first.result.suite,
      name: first.result.name,
      totalRuns,
      failures,
      failRate: round(failRate),
      contradictoryCommits,
      comparableCommits,
      flakiness: round(flakiness),
      confidence: confidenceOf(comparableCommits, totalRuns),
      rationale,
      lastFailureMessage: lastFailure?.result.message,
      lastSeenAt: last.at,
    });
  }

  return verdicts.sort(
    (a, b) => b.flakiness - a.flakiness || b.totalRuns - a.totalRuns || a.id.localeCompare(b.id),
  );
}

function collect(runs: TestRun[]): Map<string, Observation[]> {
  const byTest = new Map<string, Observation[]>();
  for (const run of runs) {
    for (const result of run.results) {
      const bucket = byTest.get(result.id);
      const observation: Observation = { at: run.at, commit: run.commit, result };
      if (bucket) bucket.push(observation);
      else byTest.set(result.id, [observation]);
    }
  }
  return byTest;
}

/** 같은 커밋에서 2회 이상 실행된 경우만 세고, 그 중 결과가 갈린 것을 찾는다. */
function commitEvidence(observations: Observation[]): {
  contradictoryCommits: number;
  comparableCommits: number;
} {
  const byCommit = new Map<string, Set<string>>();
  const runCount = new Map<string, number>();

  for (const o of observations) {
    if (!o.commit) continue;
    runCount.set(o.commit, (runCount.get(o.commit) ?? 0) + 1);
    const statuses = byCommit.get(o.commit) ?? new Set<string>();
    statuses.add(o.result.status);
    byCommit.set(o.commit, statuses);
  }

  let comparable = 0;
  let contradictory = 0;
  for (const [commit, statuses] of byCommit) {
    if ((runCount.get(commit) ?? 0) < 2) continue;
    comparable += 1;
    if (statuses.has("pass") && statuses.has("fail")) contradictory += 1;
  }
  return { contradictoryCommits: contradictory, comparableCommits: comparable };
}

/** 시간순으로 통과↔실패가 몇 번 뒤바뀌었는지. 회귀와 플레이키를 가르는 신호다. */
function countTransitions(observations: Observation[]): number {
  let transitions = 0;
  for (let i = 1; i < observations.length; i += 1) {
    const previous = observations[i - 1];
    const current = observations[i];
    if (previous && current && previous.result.status !== current.result.status) {
      transitions += 1;
    }
  }
  return transitions;
}

function confidenceOf(comparableCommits: number, totalRuns: number): Confidence {
  if (comparableCommits >= 3) return "high";
  if (comparableCommits >= 1 || totalRuns >= 8) return "medium";
  return "low";
}

function round(value: number): number {
  return Math.round(value * 1000) / 1000;
}
