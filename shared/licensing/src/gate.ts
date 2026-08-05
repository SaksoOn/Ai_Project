import { verifyLicense } from "./gumroad";
import {
  DAY_MS,
  type Deps,
  type Entitlement,
  type LicenseConfig,
  type PersistedState,
  type RevocationReason,
  type Storage,
} from "./types";

const STATE_KEY = "toolworks.licensing.state";

export type ActivationResult =
  | { ok: true; entitlement: Entitlement }
  | { ok: false; reason: RevocationReason | "offline"; message: string };

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
export class LicenseGate {
  private readonly productId: string;
  private readonly trialMs: number;
  private readonly reverifyMs: number;
  private readonly graceMs: number;
  private readonly now: () => number;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(
    config: LicenseConfig,
    private readonly storage: Storage,
    deps: Deps = {},
  ) {
    this.productId = config.productId;
    this.trialMs = (config.trialDays ?? 7) * DAY_MS;
    this.reverifyMs = (config.reverifyAfterDays ?? 7) * DAY_MS;
    this.graceMs = (config.offlineGraceDays ?? 14) * DAY_MS;
    this.now = deps.now ?? (() => Date.now());
    this.fetchImpl = deps.fetch ?? globalThis.fetch;
  }

  /** 현재 사용 권한. 확장이 켜질 때와 기능을 쓸 때 호출한다. */
  async check(): Promise<Entitlement> {
    const state = this.read();
    const now = await this.tick(state);

    if (state.revokedReason) {
      return { status: "revoked", reason: state.revokedReason };
    }
    if (state.licenseKey) {
      return await this.checkLicensed(state, state.licenseKey, now);
    }
    return await this.checkTrial(state, now);
  }

  /** 사용자가 라이선스 키를 입력했을 때. 최초 1회는 네트워크가 필요하다. */
  async activate(rawKey: string): Promise<ActivationResult> {
    const key = rawKey.trim();
    if (!key) {
      return { ok: false, reason: "invalid-key", message: "라이선스 키를 입력해 주세요." };
    }

    const result = await verifyLicense(this.productId, key, this.fetchImpl);

    if (result.outcome === "unreachable") {
      return {
        ok: false,
        reason: "offline",
        message:
          `Gumroad에 연결하지 못했습니다 (${result.detail}). ` +
          "최초 활성화에는 인터넷 연결이 한 번 필요합니다. 이후에는 오프라인에서도 동작합니다.",
      };
    }
    if (result.outcome === "revoked") {
      return { ok: false, reason: result.reason, message: describeRevocation(result.reason) };
    }

    const now = this.now();
    const state = this.read();
    await this.write({
      ...state,
      licenseKey: key,
      lastVerifiedAt: now,
      revokedReason: undefined,
    });
    return {
      ok: true,
      entitlement: { status: "licensed", key, lastVerifiedAt: now, stale: false },
    };
  }

  /** 기기 변경 등으로 라이선스를 해제할 때. 체험 기록은 건드리지 않는다. */
  async deactivate(): Promise<void> {
    const state = this.read();
    await this.write({
      ...state,
      licenseKey: undefined,
      lastVerifiedAt: undefined,
      revokedReason: undefined,
    });
  }

  // ── 내부 ────────────────────────────────────────────────

  private async checkLicensed(
    state: PersistedState,
    key: string,
    now: number,
  ): Promise<Entitlement> {
    const lastVerifiedAt = state.lastVerifiedAt ?? 0;
    const age = now - lastVerifiedAt;

    if (age < this.reverifyMs) {
      return { status: "licensed", key, lastVerifiedAt, stale: false };
    }

    const result = await verifyLicense(this.productId, key, this.fetchImpl);

    if (result.outcome === "valid") {
      await this.write({ ...state, lastVerifiedAt: now });
      return { status: "licensed", key, lastVerifiedAt: now, stale: false };
    }

    if (result.outcome === "revoked") {
      await this.write({ ...state, revokedReason: result.reason });
      return { status: "revoked", reason: result.reason };
    }

    // 연결 실패 — 유예 기간 안이면 그대로 쓴다. 이 분기가 이 클래스의 존재 이유다.
    if (age < this.reverifyMs + this.graceMs) {
      return { status: "licensed", key, lastVerifiedAt, stale: true };
    }

    await this.write({ ...state, revokedReason: "offline-grace-expired" });
    return { status: "revoked", reason: "offline-grace-expired" };
  }

  private async checkTrial(state: PersistedState, now: number): Promise<Entitlement> {
    let startedAt = state.trialStartedAt;
    if (startedAt === undefined) {
      startedAt = now;
      await this.write({ ...state, trialStartedAt: startedAt });
    }

    const endsAt = startedAt + this.trialMs;
    if (now >= endsAt) {
      return { status: "expired", reason: "trial-ended" };
    }
    return {
      status: "trial",
      endsAt,
      daysRemaining: Math.max(0, Math.ceil((endsAt - now) / DAY_MS)),
    };
  }

  /**
   * 단조 증가하는 시각을 돌려주고 앵커를 갱신한다.
   *
   * 시계를 되돌리면 `raw < anchor`가 되어 앵커가 그대로 쓰인다 — 되돌린 시간은
   * 인정되지 않는다. 반대로 시계가 크게 앞서면 앵커도 따라 올라가는데, 이건 감수한다.
   * 신뢰할 수 있는 외부 시각 없이는 "6개월 만에 열었다"와 "시계가 틀렸다"를 구분할 수 없고,
   * 그걸 구분하려고 서버를 두면 이 설계의 전제(서버 없음)가 무너진다.
   */
  private async tick(state: PersistedState): Promise<number> {
    const raw = this.now();
    const effective = Math.max(raw, state.clockAnchor ?? raw);
    if (effective !== state.clockAnchor) {
      state.clockAnchor = effective;
      await this.write(state);
    }
    return effective;
  }

  private read(): PersistedState {
    return this.storage.get<PersistedState>(STATE_KEY) ?? {};
  }

  private async write(state: PersistedState): Promise<void> {
    await this.storage.set(STATE_KEY, state);
  }
}

export function describeRevocation(reason: RevocationReason): string {
  switch (reason) {
    case "invalid-key":
      return "라이선스 키를 찾을 수 없습니다. 구매 확인 메일의 키를 다시 확인해 주세요.";
    case "refunded":
      return "환불된 구매입니다. 다시 구매하시면 바로 사용하실 수 있습니다.";
    case "disputed":
      return "결제 분쟁이 등록된 구매입니다. 문의를 남겨주시면 확인해 드리겠습니다.";
    case "subscription-ended":
      return "구독이 종료되었습니다. 갱신하시면 바로 사용하실 수 있습니다.";
    case "offline-grace-expired":
      return "오랫동안 라이선스를 확인하지 못했습니다. 인터넷에 연결한 뒤 다시 시도해 주세요.";
  }
}
