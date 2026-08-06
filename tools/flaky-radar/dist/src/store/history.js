"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.HistoryStore = exports.DEFAULT_MAX_RUNS = void 0;
exports.appendRun = appendRun;
exports.parseHistory = parseHistory;
exports.serializeHistory = serializeHistory;
exports.memoryIO = memoryIO;
const types_1 = require("../types");
/** 이력이 무한정 커지지 않게 막는다. 실행 200회면 판정에 충분하고도 남는다. */
exports.DEFAULT_MAX_RUNS = 200;
/**
 * 실행 하나를 이력에 더한다.
 *
 * 같은 runId가 다시 들어오면 무시한다. 파일 감시자는 저장 한 번에 이벤트를
 * 두세 번 쏘는 일이 흔한데, 그걸 그대로 받으면 같은 실행이 중복 집계되어
 * 판정이 통째로 틀어진다.
 */
function appendRun(history, run, maxRuns = exports.DEFAULT_MAX_RUNS) {
    if (history.runs.some((existing) => existing.runId === run.runId)) {
        return history;
    }
    const runs = [...history.runs, run]
        .sort((a, b) => a.at - b.at)
        .slice(-maxRuns);
    return { version: 1, runs };
}
/**
 * 저장된 JSON을 읽는다.
 *
 * 손상된 파일 때문에 확장이 죽으면 안 된다. 읽을 수 없으면 빈 이력으로 시작한다 —
 * 이력을 잃는 것이 확장이 안 켜지는 것보다 낫다.
 */
function parseHistory(raw) {
    if (!raw)
        return types_1.EMPTY_HISTORY;
    try {
        const parsed = JSON.parse(raw);
        if (parsed?.version !== 1 || !Array.isArray(parsed.runs))
            return types_1.EMPTY_HISTORY;
        return { version: 1, runs: parsed.runs.filter(isRun) };
    }
    catch {
        return types_1.EMPTY_HISTORY;
    }
}
function serializeHistory(history) {
    return JSON.stringify(history);
}
function isRun(value) {
    if (typeof value !== "object" || value === null)
        return false;
    const run = value;
    return (typeof run.runId === "string" &&
        typeof run.at === "number" &&
        Array.isArray(run.results));
}
/** 파일 하나에 이력을 담는 저장소. */
class HistoryStore {
    io;
    maxRuns;
    constructor(io, maxRuns = exports.DEFAULT_MAX_RUNS) {
        this.io = io;
        this.maxRuns = maxRuns;
    }
    async load() {
        return parseHistory(await this.io.read());
    }
    async append(run) {
        const next = appendRun(await this.load(), run, this.maxRuns);
        await this.io.write(serializeHistory(next));
        return next;
    }
    async clear() {
        await this.io.write(serializeHistory(types_1.EMPTY_HISTORY));
    }
}
exports.HistoryStore = HistoryStore;
/** 테스트·개발용 인메모리 IO. */
function memoryIO(initial) {
    let contents = initial;
    return {
        read: async () => contents,
        write: async (next) => {
            contents = next;
        },
        current: () => contents,
    };
}
//# sourceMappingURL=history.js.map