"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.verifyLicense = verifyLicense;
const VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify";
const TIMEOUT_MS = 10_000;
/**
 * 구매가 더 이상 유효하지 않은지 판단한다.
 *
 * 필드가 없을 수도 있다고 보고 방어적으로 읽는다. Gumroad가 응답 형태를 바꿔도
 * 유료 사용자가 갑자기 잠기지 않아야 한다 — 확실한 취소 신호가 있을 때만 revoke한다.
 */
function revocationOf(purchase) {
    if (!purchase)
        return null;
    if (purchase.refunded === true)
        return "refunded";
    if (purchase.disputed === true || purchase.chargebacked === true)
        return "disputed";
    const ended = purchase.subscription_cancelled_at ??
        purchase.subscription_ended_at ??
        purchase.subscription_failed_at;
    if (typeof ended === "string" && ended.length > 0)
        return "subscription-ended";
    return null;
}
async function verifyLicense(productId, licenseKey, fetchImpl = globalThis.fetch) {
    const body = new URLSearchParams({
        product_id: productId,
        license_key: licenseKey,
        // 좌석 수를 세지 않는다. 같은 사용자가 여러 기기에서 쓰는 것을 막을 이유가 없고,
        // 재검증마다 카운터가 올라가면 사용량 지표가 오염된다.
        increment_uses_count: "false",
    });
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    let response;
    try {
        response = await fetchImpl(VERIFY_URL, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString(),
            signal: controller.signal,
        });
    }
    catch (error) {
        return { outcome: "unreachable", detail: describe(error) };
    }
    finally {
        clearTimeout(timer);
    }
    // 404는 Gumroad가 "그런 라이선스 없음"을 알리는 방식이다 — 이건 확실한 무효다.
    if (response.status === 404) {
        return { outcome: "revoked", reason: "invalid-key" };
    }
    // 그 외 비정상 응답(5xx, 429 등)은 서버 문제이지 사용자 문제가 아니다.
    if (!response.ok) {
        return { outcome: "unreachable", detail: `HTTP ${response.status}` };
    }
    let data;
    try {
        data = (await response.json());
    }
    catch (error) {
        return { outcome: "unreachable", detail: `잘못된 JSON 응답: ${describe(error)}` };
    }
    if (data.success !== true) {
        return { outcome: "revoked", reason: "invalid-key" };
    }
    const revoked = revocationOf(data.purchase);
    if (revoked)
        return { outcome: "revoked", reason: revoked };
    return { outcome: "valid", uses: typeof data.uses === "number" ? data.uses : 0 };
}
function describe(error) {
    if (error instanceof Error) {
        return error.name === "AbortError" ? "요청 시간 초과" : error.message;
    }
    return String(error);
}
//# sourceMappingURL=gumroad.js.map