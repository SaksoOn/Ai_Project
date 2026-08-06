import type { FlakyVerdict, History } from "../types";
export interface AnalyzeOptions {
    /** 이 횟수 미만으로 실행된 테스트는 판정하지 않는다. 기본 2. */
    minRuns?: number;
}
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
export declare function analyze(history: History, options?: AnalyzeOptions): FlakyVerdict[];
