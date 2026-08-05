/** 사용자가 지금 무엇을 쓸 수 있는가. */
export type Entitlement =
  | { status: "trial"; daysRemaining: number; endsAt: number }
  | { status: "licensed"; key: string; lastVerifiedAt: number; stale: boolean }
  | { status: "expired"; reason: "trial-ended" }
  | { status: "revoked"; reason: RevocationReason };

export type RevocationReason =
  | "invalid-key"
  | "refunded"
  | "disputed"
  | "subscription-ended"
  | "offline-grace-expired";

/**
 * 저장소 추상화.
 *
 * VS Code API에 직접 의존하면 테스트가 불가능해진다. 확장에서는
 * `context.globalState`를 감싸 넘기고, 테스트에서는 인메모리 구현을 쓴다.
 */
export interface Storage {
  get<T>(key: string): T | undefined;
  set<T>(key: string, value: T): Promise<void>;
}

export interface LicenseConfig {
  /** Gumroad 제품 ID. 2023-01-09 이후 생성된 제품은 permalink가 아니라 이 값을 쓴다. */
  productId: string;
  /** 체험 기간. 기본 7일 — 전환율 실증이 가장 좋은 값. */
  trialDays?: number;
  /** 라이선스 재검증 주기. 기본 7일. */
  reverifyAfterDays?: number;
  /**
   * 오프라인 유예. 기본 14일.
   *
   * 비행기에서 코딩하는데 확장이 잠기는 것이 최악의 사용자 경험이다.
   * 마지막 성공 검증으로부터 이 기간까지는 네트워크가 없어도 계속 동작한다.
   */
  offlineGraceDays?: number;
}

export interface Deps {
  now?: () => number;
  fetch?: typeof globalThis.fetch;
}

/** 저장되는 상태. 키에 접두사를 붙여 확장의 다른 상태와 충돌하지 않게 한다. */
/**
 * 저장되는 상태.
 *
 * 각 필드에 `| undefined`를 명시한 것은 의도적이다. `exactOptionalPropertyTypes` 아래에서
 * 해제(deactivate) 시 `{ ...state, licenseKey: undefined }` 형태로 값을 지울 수 있어야 한다.
 */
export interface PersistedState {
  trialStartedAt?: number | undefined;
  licenseKey?: string | undefined;
  lastVerifiedAt?: number | undefined;
  revokedReason?: RevocationReason | undefined;
  /**
   * 지금까지 관측한 가장 큰 시각.
   *
   * 체험 만료를 피하려고 시스템 시계를 되돌리는 것을 무력화한다.
   * 되돌린 사용자를 처벌하지 않고, 되돌린 시간을 인정하지 않을 뿐이다.
   */
  clockAnchor?: number | undefined;
}

export const DAY_MS = 86_400_000;
