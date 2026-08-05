import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  appendRun,
  HistoryStore,
  memoryIO,
  parseHistory,
  serializeHistory,
} from "../src/store/history";
import { EMPTY_HISTORY, type TestRun } from "../src/types";

function run(runId: string, at: number): TestRun {
  return {
    runId,
    at,
    commit: "abc",
    results: [{ id: "S › t", suite: "S", name: "t", status: "pass", durationMs: 1 }],
  };
}

describe("이력 누적", () => {
  it("실행을 더한다", () => {
    const h = appendRun(EMPTY_HISTORY, run("a", 1000));
    assert.equal(h.runs.length, 1);
  });

  it("같은 runId는 중복 집계하지 않는다", () => {
    // 파일 감시자는 저장 한 번에 이벤트를 여러 번 쏜다. 그대로 받으면 판정이 틀어진다.
    let h = appendRun(EMPTY_HISTORY, run("a", 1000));
    h = appendRun(h, run("a", 1000));
    h = appendRun(h, run("a", 1000));
    assert.equal(h.runs.length, 1, "중복 이벤트가 이력을 부풀리면 안 된다");
  });

  it("시간순으로 정렬한다", () => {
    let h = appendRun(EMPTY_HISTORY, run("late", 3000));
    h = appendRun(h, run("early", 1000));
    assert.deepEqual(h.runs.map((r) => r.runId), ["early", "late"]);
  });

  it("상한을 넘으면 오래된 것부터 버린다", () => {
    let h = EMPTY_HISTORY;
    for (let i = 0; i < 10; i += 1) h = appendRun(h, run(`r${i}`, 1000 + i), 3);
    assert.equal(h.runs.length, 3);
    assert.deepEqual(h.runs.map((r) => r.runId), ["r7", "r8", "r9"]);
  });
});

describe("이력 읽기 — 손상돼도 확장이 죽지 않아야 한다", () => {
  it("정상 JSON을 읽는다", () => {
    const h = appendRun(EMPTY_HISTORY, run("a", 1000));
    assert.deepEqual(parseHistory(serializeHistory(h)), h);
  });

  it("빈 값은 빈 이력이다", () => {
    assert.deepEqual(parseHistory(undefined), EMPTY_HISTORY);
    assert.deepEqual(parseHistory(""), EMPTY_HISTORY);
  });

  it("깨진 JSON은 빈 이력으로 시작한다", () => {
    // 이력을 잃는 것이 확장이 안 켜지는 것보다 낫다.
    assert.deepEqual(parseHistory("{망가진"), EMPTY_HISTORY);
  });

  it("모르는 버전은 버린다", () => {
    assert.deepEqual(parseHistory('{"version":99,"runs":[]}'), EMPTY_HISTORY);
  });

  it("형태가 이상한 run은 걸러낸다", () => {
    const raw = '{"version":1,"runs":[{"runId":"ok","at":1,"results":[]},{"쓰레기":true},null]}';
    assert.equal(parseHistory(raw).runs.length, 1);
  });
});

describe("HistoryStore", () => {
  it("불러오기·더하기·비우기가 파일에 반영된다", async () => {
    const io = memoryIO();
    const store = new HistoryStore(io);

    assert.deepEqual(await store.load(), EMPTY_HISTORY);

    await store.append(run("a", 1000));
    await store.append(run("b", 2000));
    assert.equal((await store.load()).runs.length, 2);

    await store.append(run("b", 2000));
    assert.equal((await store.load()).runs.length, 2, "중복은 저장 후에도 걸러져야 한다");

    await store.clear();
    assert.equal((await store.load()).runs.length, 0);
  });
});
