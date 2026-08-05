# 개발 환경

## 니치 하네스 (Python)

```bash
pip install PyYAML
python3 engine/niche/score.py     # → NICHES.md 생성
```

후보를 추가하려면 `engine/niche/candidates.yaml`에 **근거(evidence)와 함께** 넣는다.
근거가 없으면 채점되지 않는다.

## 라이선스 모듈 (TypeScript)

```bash
cd shared/licensing
npm install
npm test        # 빌드 + 테스트 24종
```

이 모듈은 모든 확장이 공유한다. 확장에서:

```ts
import { LicenseGate, memento } from "@toolworks/licensing";

const gate = new LicenseGate({ productId: "GUMROAD_PRODUCT_ID" }, memento(context.globalState));
const entitlement = await gate.check();
```

### 이 모듈이 양보하지 않는 두 가지

1. **네트워크 실패로 유료 사용자를 잠그지 않는다.** 마지막 성공 검증 이후 재검증 7일 +
   유예 14일 동안은 오프라인에서도 동작한다. 비행기에서 확장이 잠기는 것이 최악의 경험이다.
2. **시계를 되돌려도 체험이 늘어나지 않는다.** 관측한 최대 시각을 앵커로 저장해
   되돌린 시간을 인정하지 않는다. 되돌린 사용자를 처벌하지는 않는다.

Gumroad 라이선스 검증에는 **판매자 API 키가 필요 없다.** 그래서 자체 서버 없이
확장이 직접 검증할 수 있고, 고정비가 0원으로 유지된다.
