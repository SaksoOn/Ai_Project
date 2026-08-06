import type { TestRun } from "../types";
export interface ParseOptions {
    runId: string;
    at: number;
    commit?: string | undefined;
}
export declare class JUnitParseError extends Error {
}
export declare function parseJUnit(xml: string, options: ParseOptions): TestRun;
