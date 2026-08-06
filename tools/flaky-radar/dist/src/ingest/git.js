"use strict";
/**
 * 현재 커밋 SHA를 알아낸다.
 *
 * git 명령을 실행하지 않고 `.git` 파일을 직접 읽는다. 이유:
 *   - 자식 프로세스를 띄우지 않아 빠르고, 테스트가 끝날 때마다 돌아도 부담이 없다
 *   - git 실행 파일이 없거나 PATH에 없어도 동작한다
 *   - 외부 명령 실행 권한을 요구하지 않는다
 *
 * 커밋을 못 찾아도 문제가 되지 않게 설계했다. 분석은 커밋 정보가 없으면
 * 전환 횟수 기반 추정으로 자동으로 넘어간다.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveCommit = resolveCommit;
const SHA = /^[0-9a-f]{40}$/i;
async function resolveCommit(git) {
    const head = (await git.read("HEAD"))?.trim();
    if (!head)
        return undefined;
    // 분리된 HEAD — SHA가 그대로 들어 있다.
    if (SHA.test(head))
        return head.toLowerCase();
    const match = /^ref:\s*(.+)$/.exec(head);
    if (!match?.[1])
        return undefined;
    const ref = match[1].trim();
    // 느슨한 ref 파일이 있으면 그걸 쓴다.
    const loose = (await git.read(ref))?.trim();
    if (loose && SHA.test(loose))
        return loose.toLowerCase();
    // 없으면 packed-refs를 뒤진다. `git gc` 이후에는 이쪽에만 남는다.
    return findInPackedRefs(await git.read("packed-refs"), ref);
}
function findInPackedRefs(contents, ref) {
    if (!contents)
        return undefined;
    for (const line of contents.split("\n")) {
        const trimmed = line.trim();
        // 주석(#)과 peeled 태그(^)는 건너뛴다.
        if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("^"))
            continue;
        const [sha, name] = trimmed.split(/\s+/, 2);
        if (name === ref && sha && SHA.test(sha))
            return sha.toLowerCase();
    }
    return undefined;
}
//# sourceMappingURL=git.js.map