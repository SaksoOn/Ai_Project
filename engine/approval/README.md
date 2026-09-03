# 전자결재 — 양식 정의와 문서 생성

사내 그룹웨어(KT BizOffice)에서 실제로 쓰는 것은 **메신저**와 **전자결재** 둘뿐이다.
이 도구는 그중 전자결재만 다룬다.

## 지금 하는 일 (Phase 0)

품의·기안·계출·출장명령서를 **YAML 스키마로 정의**하고, 값을 채우면
**붙여넣기용 평문**과 **인쇄용 A4 HTML**을 만든다.

```
new → 편집기에서 값 채움 → build → 평문을 기존 그룹웨어에 붙여넣어 상신
                                → HTML은 Ctrl+P 로 PDF 보관
```

서버도, 사내 승인도, 회사 인프라도 필요 없다. 로컬에서만 돈다.

**이 단계의 진짜 산출물은 문서가 아니라 스키마다.** 회사 양식을 데이터로 정확히
표현하는 작업은 어차피 해야 하고, 여기서 만든 스키마는 나중에 결재 워크플로를
붙일 때 한 줄도 안 고치고 그대로 쓴다. **여기서 멈춰도 손해가 없다.**

## 쓰는 법

```bash
pip install PyYAML

python3 -m engine.approval.generate doctor            # 뭐가 왜 안 되는지 한 화면에
python3 -m engine.approval.generate list              # 양식 목록
python3 -m engine.approval.generate show 출장명령서    # 필드·결재선 확인
python3 -m engine.approval.generate new 출장명령서     # 초안 파일 생성 → drafts/
python3 -m engine.approval.generate build drafts/....yaml   # → dist/approval/
```

## 사내 실제 규정 쓰기

저장소에 든 양식 4종은 **일반적인 표준 양식**이다. 사내 실제 전결 규정(금액 기준,
직위명)은 저장소 루트의 `forms.local/` 에 같은 `code` 로 두면 그쪽이 이긴다.
`forms.local/` 은 gitignore 돼 있다 — **회사 규정이 저장소에 올라가지 않는다.**

```bash
mkdir -p forms.local
cp engine/approval/forms/trip_order.yaml forms.local/
# forms.local/trip_order.yaml 을 사내 규정에 맞게 고친다
python3 -m engine.approval.generate doctor   # 덮어썼는지 확인
```

## 양식 정의

```yaml
code: TRIP_ORDER
name: 출장명령서
fields:
  - {key: budget, label: 예상경비, type: money, required: true}
  - key: transport
    label: 교통편
    type: select
    options: [자가용, 항공, 철도, 버스, 기타]

approval_line:
  default: [팀장, 부서장]
  rules:
    - when: "budget > 3000000"          # 위에서부터 먼저 맞는 규칙이 이긴다
      line: [팀장, 부서장, 재무팀장, 대표]
```

필드 타입: `text` `textarea` `date` `money` `number` `select` `user_list` `checkbox`

**`approval_line.rules` 가 이 도구의 핵심이다.** 금액별로 결재선이 갈리는 것은 한국
기업의 표준 패턴인데, 규정이 바뀔 때마다 코드를 고치는 대신 YAML 한 줄을 고친다.
기성 그룹웨어가 정확히 못 맞추는 지점이 여기고, 자체 구축을 정당화하는 유일한 근거다.

## 설계에서 양보하지 않은 것

**1. 승인하지 않은 결재자 칸에는 도장이 찍히지 않는다.**
기안자(담당) 칸만 날인된다 — 그건 결재가 아니라 "작성했음"을 뜻하고 관례가 그렇다.
승인되지 않은 문서가 승인된 것처럼 보이면 그 순간 이 도구는 위조 도구가 된다.

**2. 결재선 조건식의 오타는 조용히 넘어가지 않는다.**
`buget > 100` 처럼 필드명을 틀리면 조건이 거짓이 되어 기본 결재선으로 떨어진다.
금액이 큰데 재무팀장이 빠진 문서가 그대로 올라가면 규정 위반이고 아무도 모른다.
그래서 **양식을 읽는 시점에** 없는 필드를 참조하는 규칙을 거부한다.

**3. 조건식에 `eval()` 을 쓰지 않는다.**
양식 파일은 결국 관리자가 편집하게 될 물건이다. `ast` 로 파싱해 비교·논리·사칙연산
노드만 통과시킨다. 함수 호출·속성 접근·첨자는 문법 단계에서 막힌다.

**4. 문서번호를 자동 생성하지 않는다.**
진짜 문서번호는 상신받은 그룹웨어가 매긴다. 여기서 그럴듯한 번호를 만들면
정본이 아닌 번호가 문서에 박혀 나중에 대조할 때 혼란만 준다.

**5. 화면·인쇄·PDF가 같은 HTML에서 나온다.**
따로 만들면 반드시 어긋나고, 한국 결재 문서는 종이로 뽑았을 때 기존 양식과 같아야
감사·세무에서 통과한다. 본문 폭은 화면·인쇄 양쪽 다 180mm다.

## 이 도구가 하지 않는 것

- **메신저** — Mattermost·잔디·카카오워크가 무료/저가로 있다. 자체 메신저는
  24시간 장애 대응 부담만 남긴다.
- **실제 결재 처리** — 승인·반려·보관은 아직 기존 그룹웨어가 한다. Phase 1의 일이다.
- **회사 데이터 보관** — `drafts/`, `dist/approval/`, `forms.local/` 은 전부 gitignore.

## 다음 단계로 가기 전에

Phase 1(결재 워크플로)로 넘어가려면 그 전에 **반나절만** 확인할 것이 있다.

- [Rigel](https://rigelworks.io/) — 한국형 전자결재(전결/대결/후결/합의/병렬)를
  지원한다고 표방하는 오픈소스 셀프호스팅 그룹웨어. Docker + Supabase 기반.
  최근 커밋이 있고 라이선스가 사내 상업적 사용을 허용하면 **채택이 자체 구축보다 낫다.**

주 1~3시간은 만드는 데가 아니라 유지보수에 쓰는 게 맞다.

## 테스트

```bash
python3 -m unittest discover -s tests -t .
```
