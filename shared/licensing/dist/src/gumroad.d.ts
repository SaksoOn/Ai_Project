import type { RevocationReason } from "./types";
/**
 * Gumroad 검증 결과.
 *
 * `unreachable`은 `invalid`와 반드시 구분해야 한다. 네트워크 실패를 무효 라이선스로
 * 취급하면 오프라인 사용자가 잠긴다 — 이 모듈이 막으려는 바로 그 상황이다.
 */
export type VerifyResult = {
    outcome: "valid";
    uses: number;
} | {
    outcome: "revoked";
    reason: RevocationReason;
} | {
    outcome: "unreachable";
    detail: string;
};
export declare function verifyLicense(productId: string, licenseKey: string, fetchImpl?: typeof globalThis.fetch): Promise<VerifyResult>;
