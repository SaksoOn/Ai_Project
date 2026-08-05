# Flaky Test Radar

불안정한(flaky) 테스트를 찾아냅니다. **전부 로컬에서 동작하며 코드가 밖으로 나가지 않습니다.**

## 문제

테스트가 가끔 실패합니다. 재실행하면 통과합니다. "아 그거 원래 가끔 그래" 하고 넘어갑니다.

이게 반복되면 **아무도 CI를 안 믿게 됩니다.** 그리고 진짜 버그가 섞여 들어와도
"또 플레이키겠지" 하고 넘어갑니다. 그런데 **어떤 테스트가 불안정한지 아무도 추적하지 않습니다.**

## 어떻게 판정하는가

근거는 두 가지이고, 강한 쪽을 우선합니다.

**1. 같은 커밋에서 결과가 갈렸는가** — 확정적 증거입니다.
코드가 그대로인데 결과가 다르면 코드가 아니라 테스트가 문제입니다.

**2. 통과와 실패가 번갈아 나타나는가** — 커밋 정보가 없을 때 씁니다.

이 두 번째가 중요합니다. **회귀와 플레이키를 구분**하기 때문입니다.

```
pass pass pass fail fail fail   → 전환 1회 → 진짜 버그(회귀)
pass fail pass fail pass fail   → 전환 5회 → 불안정한 테스트
```

실패율만 보면 둘 다 50%라 구분이 안 됩니다. 전환 횟수가 이걸 가릅니다.

**항상 실패하는 테스트는 불안정한 게 아니라 그냥 깨진 겁니다.** 그렇게 표시합니다.

모든 판정에는 사람이 읽을 수 있는 근거가 붙습니다. 숫자만 던지면 아무도 믿지 않습니다.

## 지원하는 테스트 러너

**JUnit XML을 내보낼 수 있으면 전부 됩니다.**

| 러너 | 설정 |
|---|---|
| Jest | `jest-junit` 리포터 |
| Vitest | `--reporter=junit --outputFile=test-results.xml` |
| pytest | `--junitxml=junit.xml` |
| go test | `gotestsum --junitfile junit.xml` |
| Maven | surefire가 기본으로 생성 |
| Gradle | `build/test-results/test/` 에 기본 생성 |
| PHPUnit | `--log-junit junit.xml` |

러너별 파서를 따로 만들지 않은 이유입니다. 포맷 하나를 제대로 지원하면 생태계 대부분이 따라옵니다.

## 설정

| 항목 | 기본값 |
|---|---|
| `flakyRadar.resultPatterns` | `junit*.xml`, `test-results*.xml`, `TEST-*.xml`, `test-results/**/*.xml`, `surefire-reports/*.xml` |
| `flakyRadar.minRuns` | 2 |
| `flakyRadar.maxRuns` | 200 |

## 개발

```bash
npm install
npm test        # 46종 — VS Code 없이 돈다
npm run build   # extension.ts 포함 전체 타입 체크
```

로직은 전부 테스트 가능한 모듈에 있습니다. `extension.ts`는 배선만 합니다.

| 모듈 | 역할 |
|---|---|
| `src/ingest/junit.ts` | JUnit XML 파싱 |
| `src/ingest/git.ts` | 커밋 SHA 감지 (git 명령 실행 없이 `.git` 직접 읽기) |
| `src/store/history.ts` | 실행 이력 누적 (중복 이벤트 방어, 손상 파일 복구) |
| `src/analysis/flakiness.ts` | 판정 |

## 아직 남은 것

- `GUMROAD_PRODUCT_ID`가 `REPLACE_ME`입니다. Gumroad 제품을 만든 뒤 교체해야 합니다.
- `publisher`가 `TBD`입니다. 마켓플레이스 publisher 생성 후 교체합니다.
- 아이콘이 없습니다.
