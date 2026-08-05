export type TestStatus = "pass" | "fail" | "skip";

/** 한 번의 테스트 실행에서 나온 개별 테스트 결과. */
export interface TestResult {
  /** `suite › name` 형태의 안정적 식별자. 이력을 이어 붙이는 기준이다. */
  id: string;
  suite: string;
  name: string;
  status: TestStatus;
  durationMs: number;
  /** 실패 메시지. 같은 테스트가 매번 다른 이유로 깨지는지 보는 데 쓴다. */
  message?: string | undefined;
}

/** 한 번의 테스트 실행(= 결과 파일 하나). */
export interface TestRun {
  runId: string;
  at: number;
  /**
   * 커밋 SHA. 이 도구의 핵심 신호가 여기서 나온다 —
   * **같은 커밋인데 결과가 갈리면** 코드가 아니라 테스트가 문제다.
   */
  commit?: string | undefined;
  results: TestResult[];
}

export interface History {
  version: 1;
  runs: TestRun[];
}

export type Confidence = "low" | "medium" | "high";

export interface FlakyVerdict {
  id: string;
  suite: string;
  name: string;
  totalRuns: number;
  failures: number;
  failRate: number;
  /** 같은 커밋에서 pass와 fail이 모두 나온 커밋 수. 가장 강한 증거다. */
  contradictoryCommits: number;
  /** 같은 커밋에서 2회 이상 실행되어 비교가 가능했던 커밋 수. */
  comparableCommits: number;
  /** 0~1. 높을수록 불안정. */
  flakiness: number;
  confidence: Confidence;
  /** 사용자에게 왜 이 점수인지 설명한다. 숫자를 믿게 하려면 근거가 보여야 한다. */
  rationale: string;
  lastFailureMessage?: string | undefined;
  lastSeenAt: number;
}

export const EMPTY_HISTORY: History = { version: 1, runs: [] };
