export { LicenseGate, describeRevocation, type ActivationResult } from "./gate";
export { verifyLicense, type VerifyResult } from "./gumroad";
export {
  DAY_MS,
  type Deps,
  type Entitlement,
  type LicenseConfig,
  type PersistedState,
  type RevocationReason,
  type Storage,
} from "./types";

import type { Storage } from "./types";

/**
 * VS Code의 `context.globalState`를 Storage로 감싼다.
 *
 * 확장에서:
 *   const gate = new LicenseGate({ productId }, memento(context.globalState));
 *
 * globalState를 쓰는 이유는 라이선스가 워크스페이스가 아니라 사용자에게 귀속되기 때문이다.
 */
export function memento(state: {
  get<T>(key: string): T | undefined;
  // vscode.Memento는 Thenable을 돌려주지만, 여기서 vscode 타입에 의존하지 않기 위해
  // 구조적으로 호환되는 PromiseLike로 받는다.
  update(key: string, value: unknown): PromiseLike<void>;
}): Storage {
  return {
    get: <T,>(key: string) => state.get<T>(key),
    set: async <T,>(key: string, value: T) => {
      await state.update(key, value);
    },
  };
}

/** 테스트·개발용 인메모리 저장소. */
export function memoryStorage(initial: Record<string, unknown> = {}): Storage & {
  dump(): Record<string, unknown>;
} {
  const data: Record<string, unknown> = { ...initial };
  return {
    get: <T,>(key: string) => data[key] as T | undefined,
    set: async <T,>(key: string, value: T) => {
      data[key] = value;
    },
    dump: () => ({ ...data }),
  };
}
