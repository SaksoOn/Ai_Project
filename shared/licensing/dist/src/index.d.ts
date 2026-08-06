export { LicenseGate, describeRevocation, type ActivationResult } from "./gate";
export { verifyLicense, type VerifyResult } from "./gumroad";
export { DAY_MS, type Deps, type Entitlement, type LicenseConfig, type PersistedState, type RevocationReason, type Storage, } from "./types";
import type { Storage } from "./types";
/**
 * VS Code의 `context.globalState`를 Storage로 감싼다.
 *
 * 확장에서:
 *   const gate = new LicenseGate({ productId }, memento(context.globalState));
 *
 * globalState를 쓰는 이유는 라이선스가 워크스페이스가 아니라 사용자에게 귀속되기 때문이다.
 */
export declare function memento(state: {
    get<T>(key: string): T | undefined;
    update(key: string, value: unknown): PromiseLike<void>;
}): Storage;
/** 테스트·개발용 인메모리 저장소. */
export declare function memoryStorage(initial?: Record<string, unknown>): Storage & {
    dump(): Record<string, unknown>;
};
