#!/usr/bin/env python3
"""매매 복기 시트.

목적: **손실의 원인을 숫자로 드러낸다.**

이 시트가 하지 않는 것 — 종목 추천, 매매 신호, 목표가, 수익률 전망.
손실 중일 때 "만회해주는" 도구는 위험하다. 기록과 복기만 한다.

가장 중요한 두 지표:
  1. 처분효과 진단 — 손실 종목을 이익 종목보다 오래 들고 있는가
  2. 지수 대비 성과 — 그냥 지수 ETF를 들고 있었다면 어땠는가
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.chart import Reference

from ..lib import (
    ACCENT, DATE, MONEY, MUTED, NEGATIVE, PERCENT, POSITIVE, QTY,
    add_sheet, autofill_rows, bar_chart, body_cell, color_negative, color_scale,
    dropdown, guide_sheet, header_row, input_legend, kpi_card, new_workbook, note,
    section_title, set_widths, title_block,
)

FIRST, LAST = 6, 205          # 매매 200건
WATCH_FIRST, WATCH_LAST = 6, 25  # 관심종목 20개

FEE = "'설정'!$B$6"        # 편도 수수료율
TAX = "'설정'!$B$7"        # 증권거래세율
BENCH = "'설정'!$B$8"      # 벤치마크 연 수익률
YEAR = "'설정'!$B$9"       # 기준연도

T = "'매매기록'"
T_NAME = f"{T}!$A${FIRST}:$A${LAST}"
T_BUY_DATE = f"{T}!$B${FIRST}:$B${LAST}"
T_SELL_DATE = f"{T}!$C${FIRST}:$C${LAST}"
T_BUY_AMT = f"{T}!$G${FIRST}:$G${LAST}"
T_FEE = f"{T}!$I${FIRST}:$I${LAST}"
T_TAX = f"{T}!$J${FIRST}:$J${LAST}"
T_PL = f"{T}!$K${FIRST}:$K${LAST}"
T_HOLD = f"{T}!$M${FIRST}:$M${LAST}"
T_RESULT = f"{T}!$N${FIRST}:$N${LAST}"
T_BENCH = f"{T}!$Q${FIRST}:$Q${LAST}"
T_EXCESS = f"{T}!$R${FIRST}:$R${LAST}"
T_BUY_RULE = f"{T}!$U${FIRST}:$U${LAST}"
T_SELL_RULE = f"{T}!$V${FIRST}:$V${LAST}"

W = "'관심종목'"
W_NAME = f"{W}!$A${WATCH_FIRST}:$A${WATCH_LAST}"

RULE_ANSWERS = ["예", "아니오"]


def _settings(wb: Workbook) -> None:
    ws = add_sheet(wb, "설정")
    set_widths(ws, {"A": 24, "B": 16, "C": 4, "D": 62})

    row = title_block(ws, 1, "설정", "네 값만 본인 기준으로 맞춰주세요.", span=4)
    row = input_legend(ws, row, span=4)
    header_row(ws, row, ["항목", "값", "", "설명"])
    row += 1
    assert row == 6, f"수수료율은 B6이어야 한다 (현재 B{row})"

    for label, value, fmt, desc in [
        ("수수료율 (편도)", 0.00015, "0.00000%",
         "본인 증권사 기준으로 수정하세요. 매수·매도 양쪽에 각각 적용됩니다"),
        ("증권거래세율", 0.0018, "0.0000%",
         "⚠ 시장·연도에 따라 다릅니다. 반드시 본인 기준으로 확인해 수정하세요"),
        ("벤치마크 연 수익률", 0.07, PERCENT,
         "지수 값을 직접 안 넣은 매매는 이 연율로 근사 비교합니다"),
        ("기준연도", 2026, "0", "월별 집계 기준"),
    ]:
        body_cell(ws, row, 1, label, align="left")
        body_cell(ws, row, 2, value, fmt=fmt, is_input=True, bold=True)
        body_cell(ws, row, 4, desc, align="left", color=MUTED)
        row += 1

    row += 2
    row = section_title(ws, row, "이 파일이 하지 않는 것")
    for line in [
        "종목 추천, 매매 신호, 목표가, 수익률 전망을 일절 제공하지 않습니다.",
        "실시간 시세를 가져오지 않습니다. 이미 끝난 매매를 기록하고 복기하는 도구입니다.",
        "세금 계산은 참고용입니다. 실제 신고는 세무 전문가와 확인하세요.",
    ]:
        body_cell(ws, row, 1, line, align="left", color=MUTED)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        row += 1


def _watchlist(wb: Workbook) -> None:
    """관심종목 — 소수 종목 집중 전략의 규율 장치.

    매매 후에 "왜 샀는지"를 적는 것보다, **미리 정한 기준과 대조**하는 편이 훨씬 강력하다.
    기준을 먼저 적어두면 매매할 때 지켰는지 아닌지가 명확해지고, 그 차이가 진단에서
    숫자로 드러난다.
    """
    ws = add_sheet(wb, "관심종목", tab_color=POSITIVE)
    set_widths(ws, {
        "A": 20, "B": 44, "C": 34, "D": 34, "E": 12, "F": 12, "G": 30,
    })

    row = title_block(
        ws, 1, "관심종목",
        "집중해서 볼 종목만 적습니다. 매수·매도 기준을 **미리** 정해두는 것이 핵심입니다. "
        "매매할 때 이 기준을 지켰는지 기록하면, 규율을 지킨 매매와 아닌 매매의 성과 차이가 진단에 나옵니다.",
        span=7,
    )
    row = input_legend(ws, row, span=7)
    header_row(ws, row, [
        "종목명", "투자 논리 (왜 이 종목인가)", "매수 기준", "매도 기준",
        "목표 비중", "손절선", "관찰 노트",
    ])
    assert row + 1 == WATCH_FIRST

    autofill_rows(ws, WATCH_FIRST, WATCH_LAST, {
        1: {"is_input": True, "align": "left"},
        2: {"is_input": True, "align": "left"},
        3: {"is_input": True, "align": "left"},
        4: {"is_input": True, "align": "left"},
        5: {"is_input": True, "fmt": PERCENT},
        6: {"is_input": True, "fmt": PERCENT},
        7: {"is_input": True, "align": "left"},
    })

    ws.cell(row=WATCH_FIRST, column=1, value="(예시) 삼성전자")
    ws.cell(row=WATCH_FIRST, column=2, value="예시 행입니다. 지우고 쓰세요")
    ws.cell(row=WATCH_FIRST, column=3, value="예: PER 10배 이하일 때 분할 매수")
    ws.cell(row=WATCH_FIRST, column=4, value="예: 목표가 도달 또는 투자 논리가 깨졌을 때")
    ws.freeze_panes = f"B{WATCH_FIRST}"

    note(ws, WATCH_LAST + 2,
         "※ 소수 종목에 집중하면 리스크도 집중됩니다. 분산이 안 되므로 변동성이 커지고, "
         "한 종목에 오래 파고들수록 애착과 확증편향이 생기기 쉽습니다. "
         "그래서 손절선을 미리 숫자로 적어두는 것이 특히 중요합니다.", span=7)


def _trades(wb: Workbook) -> None:
    ws = add_sheet(wb, "매매기록")
    set_widths(ws, {
        "A": 20, "B": 12, "C": 12, "D": 10, "E": 13, "F": 13, "G": 14, "H": 14,
        "I": 11, "J": 11, "K": 14, "L": 10, "M": 9, "N": 8, "O": 12, "P": 12,
        "Q": 14, "R": 14, "S": 30, "T": 30, "U": 12, "V": 12,
    })

    row = title_block(
        ws, 1, "매매 기록",
        "노란 칸만 채우세요. 매도일이 비어 있으면 보유 중으로 보고 손익 계산에서 빠집니다. "
        "매수·매도 사유는 나중에 복기할 때 가장 중요한 칸입니다.",
        span=20,
    )
    row = input_legend(ws, row, span=20)
    header_row(ws, row, [
        "종목명", "매수일", "매도일", "수량", "매수단가", "매도단가",
        "매수금액", "매도금액", "수수료", "거래세", "실현손익", "수익률",
        "보유일", "결과", "매수일\n지수", "매도일\n지수", "벤치마크\n손익",
        "초과성과", "매수 사유", "매도 사유", "매수기준\n지켰나", "매도기준\n지켰나",
    ])
    assert row + 1 == FIRST

    autofill_rows(ws, FIRST, LAST, {
        1: {"is_input": True, "align": "left"},
        2: {"is_input": True, "fmt": DATE, "align": "center"},
        3: {"is_input": True, "fmt": DATE, "align": "center"},
        4: {"is_input": True, "fmt": QTY},
        5: {"is_input": True, "fmt": MONEY},
        6: {"is_input": True, "fmt": MONEY},
        7: {"formula": "=ROUND(N($D{row})*N($E{row}),0)", "fmt": MONEY},
        8: {"formula": '=IF($C{row}="",0,ROUND(N($D{row})*N($F{row}),0))', "fmt": MONEY},
        9: {"formula": f"=IF($H{{row}}=0,0,ROUND(($G{{row}}+$H{{row}})*{FEE},0))", "fmt": MONEY},
        10: {"formula": f"=IF($H{{row}}=0,0,ROUND($H{{row}}*{TAX},0))", "fmt": MONEY},
        11: {"formula": "=IF($H{row}=0,0,$H{row}-$G{row}-$I{row}-$J{row})", "fmt": MONEY},
        12: {"formula": "=IF($G{row}=0,0,IFERROR($K{row}/$G{row},0))", "fmt": PERCENT},
        13: {"formula": '=IF(OR($B{row}="",$C{row}=""),0,$C{row}-$B{row})', "fmt": QTY},
        14: {"formula": '=IF($H{row}=0,"",IF($K{row}>0,"이익",IF($K{row}<0,"손실","본전")))',
             "align": "center"},
        15: {"is_input": True, "fmt": "#,##0.00"},
        16: {"is_input": True, "fmt": "#,##0.00"},
        # 지수를 직접 넣었으면 그걸로 정확히, 아니면 설정의 연율로 근사한다.
        17: {"formula": f"=IF($H{{row}}=0,0,IF(AND(N($O{{row}})>0,N($P{{row}})>0),"
                        f"ROUND($G{{row}}*($P{{row}}/$O{{row}}-1),0),"
                        f"ROUND($G{{row}}*$M{{row}}*{BENCH}/365,0)))", "fmt": MONEY},
        18: {"formula": "=IF($H{row}=0,0,$K{row}-$Q{row})", "fmt": MONEY},
        19: {"is_input": True, "align": "left"},
        20: {"is_input": True, "align": "left"},
        21: {"is_input": True, "align": "center"},
        22: {"is_input": True, "align": "center"},
    })

    dropdown(ws, f"A{FIRST}:A{LAST}", None, source=W_NAME)
    dropdown(ws, f"U{FIRST}:U{LAST}", RULE_ANSWERS)
    dropdown(ws, f"V{FIRST}:V{LAST}", RULE_ANSWERS)
    color_negative(ws, f"K{FIRST}:L{LAST}")
    color_negative(ws, f"R{FIRST}:R{LAST}")
    ws.freeze_panes = f"B{FIRST}"

    note(ws, LAST + 2,
         "※ 매수일·매도일 지수는 선택 입력입니다. 넣으면 정확히 비교하고, 비우면 설정의 "
         "벤치마크 연 수익률로 근사합니다.\n"
         "※ '기준 지켰나'는 [관심종목]에 미리 적어둔 매수·매도 기준을 지켰는지입니다. "
         "이 답이 진단에서 가장 값진 지표가 됩니다.", span=20)


def _diagnosis(wb: Workbook) -> None:
    ws = add_sheet(wb, "진단", tab_color="B45309")
    set_widths(ws, {
        "A": 22, "B": 16, "C": 16, "D": 16, "E": 16, "F": 16, "G": 4, "H": 15, "I": 15,
    })

    closed = f'COUNTIF({T_SELL_DATE},">0")'
    wins = f'COUNTIF({T_RESULT},"이익")'
    losses = f'COUNTIF({T_RESULT},"손실")'
    avg_win = f'IFERROR(AVERAGEIF({T_RESULT},"이익",{T_PL}),0)'
    avg_loss = f'IFERROR(AVERAGEIF({T_RESULT},"손실",{T_PL}),0)'
    hold_win = f'IFERROR(AVERAGEIF({T_RESULT},"이익",{T_HOLD}),0)'
    hold_loss = f'IFERROR(AVERAGEIF({T_RESULT},"손실",{T_HOLD}),0)'

    row = title_block(ws, 1, "진단",
                      "매매기록에 입력하면 자동으로 채워집니다. 손댈 곳 없습니다.", span=9)

    for idx, (label, formula, fmt) in enumerate([
        ("총 실현손익", f"=SUM({T_PL})", MONEY),
        ("수수료+세금", f"=SUM({T_FEE})+SUM({T_TAX})", MONEY),
        ("승률", f"=IFERROR({wins}/{closed},0)", PERCENT),
        ("손익비", f"=IFERROR({avg_win}/ABS({avg_loss}),0)", "0.00"),
        ("지수 대비", f"=SUM({T_EXCESS})", MONEY),
        ("종료 매매", f"={closed}", QTY),
    ]):
        kpi_card(ws, row, idx + 1, label, formula, fmt)
    row += 4

    # ── 처분효과 — 이 시트의 핵심 ────────────────────────
    row = section_title(ws, row, "① 처분효과 진단 — 손절을 제때 하고 있는가")
    header_row(ws, row, ["구분", "건수", "평균 보유일", "평균 손익", "합계 손익", ""])
    row += 1
    for label, key, avg, hold in [
        ("이익 매매", "이익", avg_win, hold_win),
        ("손실 매매", "손실", avg_loss, hold_loss),
    ]:
        body_cell(ws, row, 1, label, align="left", bold=True)
        body_cell(ws, row, 2, f'=COUNTIF({T_RESULT},"{key}")', fmt=QTY)
        body_cell(ws, row, 3, f"={hold}", fmt="0.0")
        body_cell(ws, row, 4, f"={avg}", fmt=MONEY)
        body_cell(ws, row, 5, f'=SUMIF({T_RESULT},"{key}",{T_PL})', fmt=MONEY)
        row += 1

    verdict = (
        f'=IF({closed}=0,"매매 기록을 입력하면 진단이 나옵니다.",'
        f'IF({hold_loss}>{hold_win},'
        f'"⚠ 손실 종목을 이익 종목보다 "&ROUND({hold_loss}-{hold_win},1)&"일 더 오래 들고 있습니다. '
        f'손절이 늦고 이익은 짧게 끊는 패턴입니다. 손실이 계속 나는 가장 흔한 원인입니다.",'
        f'"이익 종목을 손실 종목보다 오래 보유하고 있습니다. 이 부분은 정상입니다."))'
    )
    cell = body_cell(ws, row, 1, verdict, align="left", bold=True)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    cell.font = cell.font.copy(color=NEGATIVE)
    row += 3

    # ── 규율 — 소수 종목 집중 전략의 핵심 지표 ──────────
    row = section_title(ws, row, "② 규율 — 내가 정한 기준을 지켰을 때와 아닐 때")
    header_row(ws, row, ["구분", "건수", "합계 손익", "평균 손익", "승률", ""])
    row += 1
    rule_start = row
    for label, col_range, answer in [
        ("매수기준 지킴", T_BUY_RULE, "예"),
        ("매수기준 어김", T_BUY_RULE, "아니오"),
        ("매도기준 지킴", T_SELL_RULE, "예"),
        ("매도기준 어김", T_SELL_RULE, "아니오"),
    ]:
        scope = f'{col_range},"{answer}",{T_SELL_DATE},">0"'
        body_cell(ws, row, 1, label, align="left", bold="지킴" in label)
        body_cell(ws, row, 2, f"=COUNTIFS({scope})", fmt=QTY)
        body_cell(ws, row, 3, f"=SUMIFS({T_PL},{scope})", fmt=MONEY)
        body_cell(ws, row, 4, f"=IFERROR($C{row}/$B{row},0)", fmt=MONEY)
        body_cell(ws, row, 5,
                  f'=IFERROR(COUNTIFS({col_range},"{answer}",{T_RESULT},"이익")/$B{row},0)',
                  fmt=PERCENT)
        row += 1
    color_negative(ws, f"C{rule_start}:D{row - 1}")

    kept = f'COUNTIFS({T_BUY_RULE},"예",{T_SELL_DATE},">0")'
    broke = f'COUNTIFS({T_BUY_RULE},"아니오",{T_SELL_DATE},">0")'
    avg_kept = f'IFERROR(SUMIFS({T_PL},{T_BUY_RULE},"예",{T_SELL_DATE},">0")/{kept},0)'
    avg_broke = f'IFERROR(SUMIFS({T_PL},{T_BUY_RULE},"아니오",{T_SELL_DATE},">0")/{broke},0)'
    rule_verdict = (
        f'=IF(OR({kept}=0,{broke}=0),'
        f'"기준 준수 여부를 양쪽 다 기록하면 비교가 나옵니다.",'
        f'IF({avg_kept}>{avg_broke},'
        f'"기준을 지킨 매매의 평균 손익이 어긴 매매보다 높습니다. 기준이 작동하고 있습니다.",'
        f'"⚠ 기준을 지킨 매매가 오히려 성과가 낮습니다. 기준 자체를 다시 봐야 합니다."))'
    )
    body_cell(ws, row, 1, rule_verdict, align="left", bold=True)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 3

    # ── 수수료 ──────────────────────────────────────────
    row = section_title(ws, row, "③ 비용 — 매매가 잦으면 여기서 샌다")
    header_row(ws, row, ["항목", "금액", "", "설명", "", ""])
    row += 1
    for label, formula, desc in [
        ("총 수수료", f"=SUM({T_FEE})", "매수·매도 양쪽 합계"),
        ("총 거래세", f"=SUM({T_TAX})", "매도 시에만 발생"),
        ("비용 합계", f"=SUM({T_FEE})+SUM({T_TAX})", "실현손익에서 이미 차감된 금액"),
        ("총 매수금액 대비", f"=IFERROR((SUM({T_FEE})+SUM({T_TAX}))/SUM({T_BUY_AMT}),0)",
         "투입 원금 대비 비용 비율"),
        ("비용이 없었다면", f"=SUM({T_PL})+SUM({T_FEE})+SUM({T_TAX})",
         "이 값과 총 실현손익의 차이가 매매 빈도의 대가입니다"),
    ]:
        body_cell(ws, row, 1, label, align="left")
        body_cell(ws, row, 2, formula,
                  fmt=PERCENT if "대비" in label else MONEY,
                  bold=label == "비용이 없었다면")
        body_cell(ws, row, 4, desc, align="left", color=MUTED)
        ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=6)
        row += 1
    row += 2

    # ── 지수 대비 ───────────────────────────────────────
    row = section_title(ws, row, "③ 지수 대비 — 그냥 들고 있었다면 어땠을까")
    header_row(ws, row, ["항목", "금액", "", "설명", "", ""])
    row += 1
    for label, formula, desc in [
        ("내 실현손익", f"=SUM({T_PL})", "실제 매매 결과"),
        ("지수였다면", f"=SUM({T_BENCH})", "같은 돈을 같은 기간 지수에 뒀을 경우"),
        ("초과성과", f"=SUM({T_EXCESS})", "양수면 지수보다 잘한 것, 음수면 못한 것"),
    ]:
        body_cell(ws, row, 1, label, align="left")
        body_cell(ws, row, 2, formula, fmt=MONEY, bold=label == "초과성과")
        body_cell(ws, row, 4, desc, align="left", color=MUTED)
        ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=6)
        row += 1

    excess_verdict = (
        f'=IF({closed}=0,"",IF(SUM({T_EXCESS})<0,'
        f'"⚠ 지수를 그냥 들고 있는 것보다 못했습니다. 매매 자체가 손실 원인일 수 있습니다.",'
        f'"지수보다 나은 성과입니다."))'
    )
    body_cell(ws, row, 1, excess_verdict, align="left", bold=True)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 3

    # ── 월별 ────────────────────────────────────────────
    row = section_title(ws, row, "④ 월별 실현손익 (설정의 기준연도, 매도일 기준)")
    header_row(ws, row, ["월", "실현손익", "매매 건수", "승률", "", ""])
    m_head = row
    row += 1
    m_start = row
    for m in range(1, 13):
        r = m_start + m - 1
        first = f"DATE({YEAR},{m},1)"
        last_day = f"EOMONTH({first},0)"
        rng = f'{T_SELL_DATE},">="&{first},{T_SELL_DATE},"<="&{last_day}'
        body_cell(ws, r, 1, f"{m}월", align="center")
        body_cell(ws, r, 2, f"=SUMIFS({T_PL},{rng})", fmt=MONEY)
        body_cell(ws, r, 3, f"=COUNTIFS({rng})", fmt=QTY)
        body_cell(ws, r, 4,
                  f'=IFERROR(COUNTIFS({rng},{T_RESULT},"이익")/$C{r},0)', fmt=PERCENT)
    m_end = m_start + 11
    color_negative(ws, f"B{m_start}:B{m_end}")
    bar_chart(ws, "월별 실현손익",
              Reference(ws, min_col=2, min_row=m_head, max_row=m_end),
              Reference(ws, min_col=1, min_row=m_start, max_row=m_end),
              anchor=f"H{m_head}")
    row = m_end + 3

    # ── 보유기간 분포 ───────────────────────────────────
    row = section_title(ws, row, "⑤ 보유기간 분포 — 내 매매 스타일이 실제로 무엇인가")
    header_row(ws, row, ["보유기간", "건수", "합계 손익", "평균 손익", "", ""])
    row += 1
    buckets = [
        ("1일 이하", 0, 1), ("2~7일", 2, 7), ("8~30일", 8, 30),
        ("31~90일", 31, 90), ("91~365일", 91, 365), ("1년 초과", 366, 99999),
    ]
    b_start = row
    for label, lo, hi in buckets:
        cond = f'{T_RESULT},"<>",{T_HOLD},">="&{lo},{T_HOLD},"<="&{hi}'
        body_cell(ws, row, 1, label, align="left")
        body_cell(ws, row, 2, f"=COUNTIFS({cond})", fmt=QTY)
        body_cell(ws, row, 3, f"=SUMIFS({T_PL},{cond})", fmt=MONEY)
        body_cell(ws, row, 4, f"=IFERROR($C{row}/$B{row},0)", fmt=MONEY)
        row += 1
    color_negative(ws, f"C{b_start}:D{row - 1}")
    row += 2

    # ── 종목별 ──────────────────────────────────────────
    row = section_title(ws, row, "⑥ 종목별 실현손익 (매매기록 등록 순)")
    header_row(ws, row, ["종목명", "매매 건수", "실현손익", "수수료+세금", "지수 대비", ""])
    row += 1
    p_start = row
    for offset in range(25):
        r = p_start + offset
        src = f"{T}!$A${FIRST + offset}"
        body_cell(ws, r, 1, f'=IF({src}="","",{src})', align="left")
        body_cell(ws, r, 2, f'=IF($A{r}="",0,COUNTIFS({T_NAME},$A{r},{T_SELL_DATE},">0"))', fmt=QTY)
        body_cell(ws, r, 3, f'=IF($A{r}="",0,SUMIF({T_NAME},$A{r},{T_PL}))', fmt=MONEY)
        body_cell(ws, r, 4,
                  f'=IF($A{r}="",0,SUMIF({T_NAME},$A{r},{T_FEE})+SUMIF({T_NAME},$A{r},{T_TAX}))',
                  fmt=MONEY)
        body_cell(ws, r, 5, f'=IF($A{r}="",0,SUMIF({T_NAME},$A{r},{T_EXCESS}))', fmt=MONEY)
    p_end = p_start + 24
    color_negative(ws, f"C{p_start}:E{p_end}")
    color_scale(ws, f"C{p_start}:C{p_end}")

    note(ws, p_end + 2,
         "※ 같은 종목을 여러 번 매매했다면 합산됩니다. 반복적으로 손실이 나는 종목이 있는지 보세요.",
         span=9)


def build() -> Workbook:
    wb = new_workbook()
    _settings(wb)
    _watchlist(wb)
    _trades(wb)
    _diagnosis(wb)
    guide_sheet(wb, "매매 복기 시트", [
        ("이 시트가 하는 일", [
            "손실이 왜 나는지를 숫자로 드러냅니다.",
            "대부분의 개인 투자자는 자기 매매 패턴을 모른 채 같은 실수를 반복합니다.",
            "이 시트는 그 패턴을 보여줄 뿐, 수익을 만들어주지는 않습니다.",
        ]),
        ("이 시트가 하지 않는 일", [
            "종목 추천, 매매 신호, 목표가, 수익률 전망을 일절 제공하지 않습니다.",
            "실시간 시세를 가져오지 않습니다. 끝난 매매를 기록하고 복기하는 도구입니다.",
            "손실 중일 때 '만회해주는' 도구는 위험합니다. 그래서 의도적으로 넣지 않았습니다.",
        ]),
        ("처음 한 번만", [
            "1. [설정]에서 수수료율을 본인 증권사 기준으로 고칩니다.",
            "2. 증권거래세율을 확인합니다. 시장·연도에 따라 다르니 반드시 직접 확인하세요.",
            "3. 벤치마크 연 수익률을 정합니다. 비교 기준으로만 쓰입니다.",
        ]),
        ("매매할 때마다", [
            "[매매기록]에 한 줄 추가합니다. 종목명, 매수일, 수량, 매수단가부터 넣습니다.",
            "매도하면 매도일과 매도단가를 채웁니다. 나머지는 전부 자동 계산됩니다.",
            "매도일이 비어 있으면 보유 중으로 보고 손익 계산에서 빠집니다.",
            "★ 매수 사유를 꼭 적으세요. 나중에 복기할 때 '왜 샀는지' 없으면 배울 게 없습니다.",
        ]),
        ("월 1회 복기 — 이게 핵심입니다", [
            "[진단] 시트를 봅니다. 30분이면 충분합니다.",
            "① 처분효과 — 손실 종목을 이익 종목보다 오래 들고 있다면 손절이 늦은 겁니다.",
            "② 비용 — '비용이 없었다면' 값과 실제 손익의 차이가 매매 빈도의 대가입니다.",
            "③ 지수 대비 — 음수라면 매매 자체가 손실 원인일 수 있습니다.",
            "⑤ 보유기간 분포 — 본인이 생각하는 투자 스타일과 실제가 다를 수 있습니다.",
        ]),
        ("계산 방식 (검증용)", [
            "매수금액 = 수량 × 매수단가",
            "수수료 = (매수금액 + 매도금액) × 수수료율",
            "거래세 = 매도금액 × 거래세율",
            "실현손익 = 매도금액 − 매수금액 − 수수료 − 거래세",
            "벤치마크 손익 = 지수를 넣었으면 매수금액 × (매도일지수 ÷ 매수일지수 − 1),",
            "                안 넣었으면 매수금액 × 보유일 × 연수익률 ÷ 365",
            "초과성과 = 실현손익 − 벤치마크 손익",
            "손익비 = 이익 매매 평균손익 ÷ |손실 매매 평균손익|",
        ]),
        ("⚠ 주의", [
            "세금 계산은 참고용입니다. 실제 신고는 세무 전문가와 확인하세요.",
            "이 파일은 투자 자문을 제공하지 않습니다.",
            "행이 모자라면 마지막 행을 복사해 아래로 붙여넣으면 수식이 확장됩니다.",
        ]),
    ])
    return wb
