import { type History, type TestRun } from "../types";
/** 이력이 무한정 커지지 않게 막는다. 실행 200회면 판정에 충분하고도 남는다. */
export declare const DEFAULT_MAX_RUNS = 200;
export interface HistoryIO {
    read(): Promise<string | undefined>;
    write(contents: string): Promise<void>;
}
/**
 * 실행 하나를 이력에 더한다.
 *
 * 같은 runId가 다시 들어오면 무시한다. 파일 감시자는 저장 한 번에 이벤트를
 * 두세 번 쏘는 일이 흔한데, 그걸 그대로 받으면 같은 실행이 중복 집계되어
 * 판정이 통째로 틀어진다.
 */
export declare function appendRun(history: History, run: TestRun, maxRuns?: number): History;
/**
 * 저장된 JSON을 읽는다.
 *
 * 손상된 파일 때문에 확장이 죽으면 안 된다. 읽을 수 없으면 빈 이력으로 시작한다 —
 * 이력을 잃는 것이 확장이 안 켜지는 것보다 낫다.
 */
export declare function parseHistory(raw: string | undefined): History;
export declare function serializeHistory(history: History): string;
/** 파일 하나에 이력을 담는 저장소. */
export declare class HistoryStore {
    private readonly io;
    private readonly maxRuns;
    constructor(io: HistoryIO, maxRuns?: number);
    load(): Promise<History>;
    append(run: TestRun): Promise<History>;
    clear(): Promise<void>;
}
/** 테스트·개발용 인메모리 IO. */
export declare function memoryIO(initial?: string): HistoryIO & {
    current(): string | undefined;
};
