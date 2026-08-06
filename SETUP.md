# 개발 환경

## 개인 도구 시트 (Python)

```bash
pip install openpyxl PyYAML formulas
python3 -m engine.products.build     # dist/ 에 두 시트 생성
python3 -m engine.products.verify    # 수식을 실제 계산시켜 검증
```

`formulas`는 `verify`에서만 쓴다. 빌드된 xlsx의 수식을 실제로 계산해 기대값과
대조하는 용도라 무겁다 — 빌드만 할 거면 없어도 된다. 다만 **없으면 verify가
`ModuleNotFoundError`로 죽으므로**, 검증까지 할 거면 처음부터 같이 깐다.

## 일일 업무기록 (Python, Windows 전용)

```bash
pip install openpyxl pywin32
cd tools/daily-log
cp config.example.toml config.toml   # 본인 메일 주소를 채운다
python run.py doctor                 # 뭐가 왜 안 되는지 한 화면에
```

`config.toml`의 주소를 예시값 그대로 두면 `doctor`가 잡아낸다. 안 고치면
받은 메일이 한 건도 안 걸리는데 겉으로는 정상처럼 보이기 때문이다.

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
