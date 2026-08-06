import { type Deps, type Entitlement, type LicenseConfig, type RevocationReason, type Storage } from "./types";
export type ActivationResult = {
    ok: true;
    entitlement: Entitlement;
} | {
    ok: false;
    reason: RevocationReason | "offline";
    message: string;
};
/**
 * 체험 기간과 라이선스를 관리하는 단일 진입점.
 *
 * 설계에서 양보하지 않은 두 가지:
 *
 * 1. **네트워크 실패로 유료 사용자를 잠그지 않는다.** 비행기·사내망·Gumroad 장애 어느
 *    경우든 마지막 성공 검증으로부터 `offlineGraceDays` 동안은 그대로 동작한다.
 * 2. **시계를 되돌려도 체험이 늘어나지 않는다.** 다만 되돌린 사용자를 처벌하지는 않고,
 *    되돌린 시간을 인정하지 않을 뿐이다.
 */
export declare class LicenseGate {
    private readonly storage;
    private readonly productId;
    private readonly trialMs;
    private readonly reverifyMs;
    private readonly graceMs;
    private readonly now;
    private readonly fetchImpl;
    constructor(config: LicenseConfig, storage: Storage, deps?: Deps);
    /** 현재 사용 권한. 확장이 켜질 때와 기능을 쓸 때 호출한다. */
    check(): Promise<Entitlement>;
    /** 사용자가 라이선스 키를 입력했을 때. 최초 1회는 네트워크가 필요하다. */
    activate(rawKey: string): Promise<ActivationResult>;
    /** 기기 변경 등으로 라이선스를 해제할 때. 체험 기록은 건드리지 않는다. */
    deactivate(): Promise<void>;
    private checkLicensed;
    private checkTrial;
    /**
     * 단조 증가하는 시각을 돌려주고 앵커를 갱신한다.
     *
     * 시계를 되돌리면 `raw < anchor`가 되어 앵커가 그대로 쓰인다 — 되돌린 시간은
     * 인정되지 않는다. 반대로 시계가 크게 앞서면 앵커도 따라 올라가는데, 이건 감수한다.
     * 신뢰할 수 있는 외부 시각 없이는 "6개월 만에 열었다"와 "시계가 틀렸다"를 구분할 수 없고,
     * 그걸 구분하려고 서버를 두면 이 설계의 전제(서버 없음)가 무너진다.
     */
    private tick;
    private read;
    private write;
}
export declare function describeRevocation(reason: RevocationReason): string;
