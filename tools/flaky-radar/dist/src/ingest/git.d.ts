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
export interface GitReader {
    /** 파일이 없으면 undefined. 오류를 던지지 않는다. */
    read(relativePath: string): Promise<string | undefined>;
}
export declare function resolveCommit(git: GitReader): Promise<string | undefined>;
