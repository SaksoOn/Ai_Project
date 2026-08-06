"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_test_1 = require("node:test");
const junit_1 = require("../src/ingest/junit");
const opts = { runId: "r1", at: 1000 };
(0, node_test_1.describe)("JUnit XML 파싱", () => {
    (0, node_test_1.it)("표준 testsuites 구조를 읽는다", () => {
        const xml = `<?xml version="1.0"?>
      <testsuites>
        <testsuite name="Cart" tests="2">
          <testcase classname="Cart" name="총액을 계산한다" time="0.125"/>
          <testcase classname="Cart" name="빈 장바구니를 처리한다" time="0.02"/>
        </testsuite>
      </testsuites>`;
        const run = (0, junit_1.parseJUnit)(xml, opts);
        strict_1.default.equal(run.results.length, 2);
        strict_1.default.equal(run.results[0]?.id, "Cart › 총액을 계산한다");
        strict_1.default.equal(run.results[0]?.status, "pass");
        strict_1.default.equal(run.results[0]?.durationMs, 125);
    });
    (0, node_test_1.it)("testsuite 하나만 있는 루트도 읽는다", () => {
        const xml = `<testsuite name="Solo"><testcase name="하나" time="0.1"/></testsuite>`;
        const run = (0, junit_1.parseJUnit)(xml, opts);
        strict_1.default.equal(run.results.length, 1);
        strict_1.default.equal(run.results[0]?.suite, "Solo");
    });
    (0, node_test_1.it)("중첩된 testsuite를 재귀로 훑는다", () => {
        const xml = `<testsuites>
      <testsuite name="Outer">
        <testcase name="바깥"/>
        <testsuite name="Inner"><testcase name="안쪽"/></testsuite>
      </testsuite>
    </testsuites>`;
        const run = (0, junit_1.parseJUnit)(xml, opts);
        strict_1.default.equal(run.results.length, 2);
        strict_1.default.deepEqual(run.results.map((r) => r.name).sort(), ["바깥", "안쪽"]);
    });
    (0, node_test_1.it)("failure의 message 속성을 읽는다", () => {
        const xml = `<testsuite name="S"><testcase name="t">
      <failure message="1이 2와 같기를 기대했습니다">스택 트레이스</failure>
    </testcase></testsuite>`;
        const run = (0, junit_1.parseJUnit)(xml, opts);
        strict_1.default.equal(run.results[0]?.status, "fail");
        strict_1.default.equal(run.results[0]?.message, "1이 2와 같기를 기대했습니다");
    });
    (0, node_test_1.it)("message 속성이 없으면 본문을 쓴다", () => {
        const xml = `<testsuite name="S"><testcase name="t">
      <failure>AssertionError: 실패</failure>
    </testcase></testsuite>`;
        strict_1.default.equal((0, junit_1.parseJUnit)(xml, opts).results[0]?.message, "AssertionError: 실패");
    });
    (0, node_test_1.it)("error도 실패로 본다 (예외든 단언 실패든 불안정성 판단엔 같다)", () => {
        const xml = `<testsuite name="S"><testcase name="t">
      <error message="TypeError"/>
    </testcase></testsuite>`;
        strict_1.default.equal((0, junit_1.parseJUnit)(xml, opts).results[0]?.status, "fail");
    });
    (0, node_test_1.it)("skipped를 구분한다", () => {
        const xml = `<testsuite name="S"><testcase name="t"><skipped/></testcase></testsuite>`;
        strict_1.default.equal((0, junit_1.parseJUnit)(xml, opts).results[0]?.status, "skip");
    });
    (0, node_test_1.it)("classname을 suite 이름보다 우선한다", () => {
        const xml = `<testsuite name="파일이름">
      <testcase classname="실제.클래스" name="t"/>
    </testsuite>`;
        strict_1.default.equal((0, junit_1.parseJUnit)(xml, opts).results[0]?.suite, "실제.클래스");
    });
    (0, node_test_1.it)("time이 없거나 이상해도 죽지 않는다", () => {
        const xml = `<testsuite name="S"><testcase name="t" time="나쁜값"/></testsuite>`;
        strict_1.default.equal((0, junit_1.parseJUnit)(xml, opts).results[0]?.durationMs, 0);
    });
    (0, node_test_1.it)("testsuite가 없으면 명확한 오류를 낸다", () => {
        strict_1.default.throws(() => (0, junit_1.parseJUnit)("<root><other/></root>", opts), junit_1.JUnitParseError);
    });
    (0, node_test_1.it)("커밋 정보를 실행에 함께 담는다", () => {
        const xml = `<testsuite name="S"><testcase name="t"/></testsuite>`;
        const run = (0, junit_1.parseJUnit)(xml, { ...opts, commit: "abc123" });
        strict_1.default.equal(run.commit, "abc123");
    });
});
//# sourceMappingURL=junit.test.js.map