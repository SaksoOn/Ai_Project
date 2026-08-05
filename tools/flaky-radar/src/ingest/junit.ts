import { XMLParser } from "fast-xml-parser";

import type { TestResult, TestRun, TestStatus } from "../types";

/**
 * JUnit XML을 읽는다.
 *
 * 러너별 파서를 따로 만들지 않는 이유: jest·vitest·pytest·go test·maven·gradle·
 * phpunit·rspec이 전부 JUnit XML을 낼 수 있다. 포맷 하나를 제대로 지원하면
 * 생태계 대부분이 따라온다. 유지보수 부담을 줄이는 가장 큰 결정이다.
 */
const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: "@_",
  parseAttributeValue: false,
  trimValues: true,
  // 테스트가 하나뿐이어도 배열로 받아 분기를 없앤다.
  isArray: (name) => name === "testsuite" || name === "testcase",
});

interface RawCase {
  "@_name"?: string;
  "@_classname"?: string;
  "@_time"?: string;
  failure?: unknown;
  error?: unknown;
  skipped?: unknown;
}

interface RawSuite {
  "@_name"?: string;
  testcase?: RawCase[];
  testsuite?: RawSuite[];
}

export interface ParseOptions {
  runId: string;
  at: number;
  commit?: string | undefined;
}

export class JUnitParseError extends Error {}

export function parseJUnit(xml: string, options: ParseOptions): TestRun {
  let document: Record<string, unknown>;
  try {
    document = parser.parse(xml) as Record<string, unknown>;
  } catch (error) {
    throw new JUnitParseError(
      `JUnit XML을 읽지 못했습니다: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  const roots = rootSuites(document);
  if (roots.length === 0) {
    throw new JUnitParseError("testsuite 요소를 찾지 못했습니다. JUnit XML이 맞는지 확인해 주세요.");
  }

  const results: TestResult[] = [];
  for (const suite of roots) {
    collectCases(suite, results);
  }

  return {
    runId: options.runId,
    at: options.at,
    commit: options.commit,
    results,
  };
}

/** 루트가 `<testsuites>`일 수도 `<testsuite>` 하나일 수도 있다. 둘 다 받는다. */
function rootSuites(document: Record<string, unknown>): RawSuite[] {
  const container = document["testsuites"] as { testsuite?: RawSuite[] } | undefined;
  if (container?.testsuite) return container.testsuite;

  const direct = document["testsuite"] as RawSuite[] | undefined;
  if (Array.isArray(direct)) return direct;

  return [];
}

/** testsuite는 중첩될 수 있다(gradle 등). 재귀로 훑는다. */
function collectCases(suite: RawSuite, out: TestResult[]): void {
  const suiteName = suite["@_name"] ?? "";

  for (const testcase of suite.testcase ?? []) {
    const name = testcase["@_name"];
    if (!name) continue;

    // classname이 있으면 그쪽이 더 안정적인 식별자다. 파일이 옮겨져도 잘 안 바뀐다.
    const owner = testcase["@_classname"] || suiteName || "(suite 없음)";

    out.push({
      id: `${owner} › ${name}`,
      suite: owner,
      name,
      status: statusOf(testcase),
      durationMs: seconds(testcase["@_time"]),
      message: failureMessage(testcase),
    });
  }

  for (const nested of suite.testsuite ?? []) {
    collectCases(nested, out);
  }
}

function statusOf(testcase: RawCase): TestStatus {
  // error는 failure와 구분되지만(예외 vs 단언 실패) 불안정성 판단에는 똑같이 '실패'다.
  if (testcase.failure !== undefined || testcase.error !== undefined) return "fail";
  if (testcase.skipped !== undefined) return "skip";
  return "pass";
}

function failureMessage(testcase: RawCase): string | undefined {
  const node = testcase.failure ?? testcase.error;
  if (node === undefined) return undefined;

  // <failure message="..."/> 또는 <failure>본문</failure> 또는 둘 다.
  if (typeof node === "string") return node.trim() || undefined;
  if (typeof node === "object" && node !== null) {
    const record = node as Record<string, unknown>;
    const attribute = record["@_message"];
    if (typeof attribute === "string" && attribute.trim()) return attribute.trim();
    const text = record["#text"];
    if (typeof text === "string" && text.trim()) return text.trim();
  }
  return undefined;
}

function seconds(value: string | undefined): number {
  const parsed = Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? Math.round(parsed * 1000) : 0;
}
