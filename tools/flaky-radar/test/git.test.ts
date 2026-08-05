import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { resolveCommit, type GitReader } from "../src/ingest/git";

const SHA = "a".repeat(39) + "1";

function reader(files: Record<string, string>): GitReader {
  return { read: async (path) => files[path] };
}

describe("커밋 감지", () => {
  it("일반적인 브랜치 HEAD를 따라간다", async () => {
    const git = reader({
      HEAD: "ref: refs/heads/main\n",
      "refs/heads/main": `${SHA}\n`,
    });
    assert.equal(await resolveCommit(git), SHA);
  });

  it("분리된 HEAD를 읽는다", async () => {
    assert.equal(await resolveCommit(reader({ HEAD: `${SHA}\n` })), SHA);
  });

  it("느슨한 ref가 없으면 packed-refs를 뒤진다", async () => {
    // git gc 이후에는 ref 파일이 사라지고 packed-refs에만 남는다.
    const git = reader({
      HEAD: "ref: refs/heads/main\n",
      "packed-refs": `# pack-refs with: peeled fully-peeled sorted\n${SHA} refs/heads/main\n`,
    });
    assert.equal(await resolveCommit(git), SHA);
  });

  it("packed-refs의 주석과 peeled 태그를 건너뛴다", async () => {
    const git = reader({
      HEAD: "ref: refs/heads/main\n",
      "packed-refs":
        `# comment\n${"b".repeat(40)} refs/tags/v1\n^${"c".repeat(40)}\n${SHA} refs/heads/main\n`,
    });
    assert.equal(await resolveCommit(git), SHA);
  });

  it("대문자 SHA를 소문자로 맞춘다", async () => {
    // 커밋 문자열이 곧 그룹 키다. 대소문자가 섞이면 같은 커밋이 둘로 갈라진다.
    const git = reader({ HEAD: `${SHA.toUpperCase()}\n` });
    assert.equal(await resolveCommit(git), SHA);
  });

  it("git 저장소가 아니면 조용히 undefined를 낸다", async () => {
    assert.equal(await resolveCommit(reader({})), undefined);
  });

  it("ref를 어디서도 못 찾으면 undefined를 낸다", async () => {
    const git = reader({ HEAD: "ref: refs/heads/사라진브랜치\n" });
    assert.equal(await resolveCommit(git), undefined);
  });

  it("HEAD가 이상해도 죽지 않는다", async () => {
    assert.equal(await resolveCommit(reader({ HEAD: "쓰레기\n" })), undefined);
    assert.equal(await resolveCommit(reader({ HEAD: "" })), undefined);
  });
});
