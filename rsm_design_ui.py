from __future__ import annotations

import html

import streamlit as st

from rsm_config import RESPONSE_COLUMNS, term_help
from rsm_design import *
from rsm_i18n import get_language, t
from rsm_state import round_decimal_input_state


def render_design_print_button(
    design_preview,
    preview_columns: list[str],
    preview_labels: dict[str, str],
    design_name: str,
    factor_count: int,
    display_ranges: dict[str, tuple[float, float]],
    center_points: int,
    batch_count: int,
    random_seed: int,
    print_notes: str,
) -> None:
    print_df = design_preview.loc[:, preview_columns].rename(
        columns={
            "StdOrder": t("설계순번"),
            "Run": t("실행순번"),
            "Batch": t("배치번호"),
            "PointType": t("포인트타입"),
            **{
                column: preview_labels.get(column, column).replace("\n", " / ")
                for column in preview_columns
                if column not in {"StdOrder", "Run", "Batch", "PointType"}
            },
        }
    )
    notes_html = html.escape(print_notes.strip()).replace("\n", "<br>")
    range_rows = "".join(
        "<tr>"
        f"<td>{html.escape(factor)}</td>"
        f"<td>{low:.10g}</td>"
        f"<td>{high:.10g}</td>"
        "</tr>"
        for factor, (low, high) in display_ranges.items()
    )
    table_html = print_df.to_html(
        index=False,
        border=0,
        na_rep="",
        escape=True,
        float_format=lambda value: f"{value:.10g}",
    )
    printable_html = f"""
    <!doctype html>
    <html lang="{get_language()}">
    <head>
      <meta charset="utf-8">
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: Arial, "Malgun Gothic", sans-serif; color: #111827; }}
        .print-button {{
          width: 100%; height: 40px; border: 1px solid #d1d5db; border-radius: 6px;
          background: #ffffff; color: #111827; font-size: 14px; font-weight: 600;
          cursor: pointer;
        }}
        .print-button:hover {{ border-color: #6b7280; background: #f9fafb; }}
        .print-sheet {{ display: none; }}
        h1 {{ margin: 0 0 12px; font-size: 22px; letter-spacing: 0; }}
        .meta {{ display: flex; gap: 22px; margin-bottom: 14px; font-size: 12px; }}
        .plan-details {{ display: flex; align-items: stretch; gap: 16px; margin-bottom: 16px; }}
        .ranges {{ width: 360px; flex: 0 0 360px; }}
        .notes {{
          flex: 1; min-height: 92px; border: 1px solid #9ca3af; padding: 8px 10px;
          font-size: 11px; line-height: 1.55; white-space: pre-wrap;
          background: repeating-linear-gradient(
            to bottom, #ffffff 0, #ffffff 22px, #e5e7eb 23px, #ffffff 24px
          );
        }}
        .notes strong {{ display: block; margin-bottom: 5px; background: #ffffff; }}
        .notes-content {{ background: #ffffff; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
        th, td {{ border: 1px solid #9ca3af; padding: 5px 6px; text-align: center; }}
        th {{ background: #e5e7eb; font-weight: 700; }}
        tr {{ break-inside: avoid; }}
        @media print {{
          @page {{ size: landscape; margin: 12mm; }}
          .print-button {{ display: none; }}
          .print-sheet {{ display: block; }}
        }}
      </style>
    </head>
    <body>
      <button class="print-button" type="button" onclick="window.print()">{t("실험계획 인쇄")}</button>
      <main class="print-sheet">
        <h1>{t("실험계획")}</h1>
        <div class="meta">
          <span><strong>{t("설계")}:</strong> {html.escape(design_name)}</span>
          <span><strong>{t("요인 수")}:</strong> {factor_count}</span>
          <span><strong>{t("중심점")}:</strong> {int(center_points)}</span>
          <span><strong>Batch:</strong> {int(batch_count)}</span>
          <span><strong>Seed:</strong> {int(random_seed)}</span>
        </div>
        <div class="plan-details">
          <table class="ranges">
            <thead><tr><th>{t("요인")}</th><th>{t("최소값")}</th><th>{t("최대값")}</th></tr></thead>
            <tbody>{range_rows}</tbody>
          </table>
          <section class="notes">
            <strong>{t("참고사항")}</strong>
            <div class="notes-content">{notes_html}</div>
          </section>
        </div>
        {table_html}
      </main>
    </body>
    </html>
    """
    st.iframe(printable_html, height=44)


def build_generated_design(
    input_nonce: int,
    normalized_response_labels: list[str],
    active_responses: list[str],
    response_labels: dict[str, str],
) -> dict[str, object]:
    st.caption(
        "요인 수·이름·범위와 설계 종류를 정합니다. Batch당 Run 수, 중심점 반복 수와 seed를 반영해 실험 순서를 랜덤화합니다.",
        help=term_help("Run", "Batch", "중심점", "seed"),
    )
    st.subheader("실험 설계 생성")
    top_cols = st.columns([1, 1, 1])
    factor_count = top_cols[0].radio("요인 수", [2, 3], index=0, horizontal=True, key=f"design_factor_count_{input_nonce}")
    design_options = ["CCD", "CCF", "CCI", "Full factorial"] if factor_count == 2 else ["CCD", "CCF", "CCI", "Box-Behnken", "Full factorial"]
    design_name = top_cols[1].selectbox(
        "실험 설계 종류",
        design_options,
        key=f"design_name_{input_nonce}",
        help=term_help("CCD", "CCF", "CCI", "Box-Behnken", "Full factorial"),
    )
    max_runs_per_batch = top_cols[2].number_input(
        "Batch당 가능 Run 수",
        min_value=2,
        max_value=200,
        value=20,
        step=1,
        key=f"design_max_runs_per_batch_{input_nonce}",
        help=term_help("Run", "Batch"),
    )
    run_cols = st.columns([1, 1])
    center_points_input = run_cols[0].number_input(
        "총 중심점 반복 수",
        min_value=1,
        max_value=60,
        value=5,
        step=1,
        key=f"design_center_points_{input_nonce}",
        help=term_help("중심점"),
    )
    random_seed = run_cols[1].number_input(
        "랜덤 실험순서 seed",
        min_value=0,
        max_value=999999,
        value=42,
        step=1,
        key=f"design_random_seed_{input_nonce}",
        help=term_help("seed"),
    )

    st.markdown("**요인 이름과 최소/최대값**")
    internal_factors = [f"X{i + 1}" for i in range(factor_count)]
    factor_labels: dict[str, str] = {}
    ranges: dict[str, tuple[float, float]] = {}
    invalid_ranges: list[str] = []
    range_cols = st.columns(factor_count)
    for idx in range(factor_count):
        factor = internal_factors[idx]
        with range_cols[idx]:
            factor_name = st.text_input(f"{factor} 이름", value=factor, key=f"{factor}_name_{input_nonce}").strip()
            display_name = factor_name or factor
            low_key = f"{factor}_min_{input_nonce}"
            high_key = f"{factor}_max_{input_nonce}"
            low = st.number_input(
                f"{display_name} 최소값",
                value=-1.0,
                step=0.0001,
                format="%.10g",
                key=low_key,
                on_change=round_decimal_input_state,
                args=(low_key,),
            )
            high = st.number_input(
                f"{display_name} 최대값",
                value=1.0,
                step=0.0001,
                format="%.10g",
                key=high_key,
                on_change=round_decimal_input_state,
                args=(high_key,),
            )
            if high <= low:
                invalid_ranges.append(f"{display_name} 최대값은 최소값보다 커야 합니다.")
            factor_labels[factor] = display_name
            ranges[factor] = (low, high)

    if invalid_ranges:
        for message in invalid_ranges:
            st.error(message)
        st.stop()

    factors = [factor_labels[factor] for factor in internal_factors]
    factor_codes = {
        display_name: internal_name
        for internal_name, display_name in factor_labels.items()
    }
    reserved_names = {"Run", "Batch", "RunInBatch", "StdOrder", "PointType", *RESPONSE_COLUMNS}
    normalized_factors = [normalize_name(factor) for factor in factors]
    normalized_reserved = {normalize_name(name) for name in reserved_names}
    if len(normalized_factors) != len(set(normalized_factors)):
        st.error("요인 이름이 중복되었습니다. 서로 다른 이름을 입력하세요.")
        st.stop()
    if any(factor in normalized_reserved for factor in normalized_factors):
        st.error(f"요인 이름은 Run, Batch, PointType, {', '.join(RESPONSE_COLUMNS)}와 같을 수 없습니다.")
        st.stop()
    if any(factor in set(normalized_response_labels) for factor in normalized_factors):
        st.error("요인 이름과 반응값 이름은 서로 달라야 합니다.")
        st.stop()

    design_info = (design_name, design_explanation(design_name, factor_count))
    base_runs = base_design_run_count(design_name, factor_count)
    center_points, batch_count, batch_warnings = resolve_batch_plan(base_runs, int(center_points_input), int(max_runs_per_batch))
    for warning in batch_warnings:
        st.warning(warning)

    design_df = make_actual_design_table(
        design_name,
        factor_count,
        ranges,
        int(center_points),
        int(random_seed),
        int(batch_count),
        int(max_runs_per_batch),
    )
    rename_map: dict[str, str] = {}
    for internal_name, display_name in factor_labels.items():
        rename_map[internal_name] = display_name
        rename_map[f"{internal_name}_coded"] = f"{display_name}_coded"
    design_df = design_df.rename(columns=rename_map)
    inactive_responses = [response for response in RESPONSE_COLUMNS if response not in active_responses]
    design_df = design_df.drop(columns=inactive_responses, errors="ignore")
    display_ranges = {factor_labels[factor]: value for factor, value in ranges.items()}

    if design_name == "CCD":
        st.warning("CCD는 회전성 때문에 축점이 입력한 최소/최대 범위 밖으로 나갈 수 있습니다. 범위를 넘기면 위험한 공정은 CCF를 고려하세요.")
    if design_name == "CCI":
        st.info("CCI는 입력한 최소/최대 범위를 넘기지 않도록 factorial 점을 안쪽으로 넣은 CCD 계열 설계입니다.")
    if design_name == "CCF":
        st.info("CCF는 축점이 각 요인의 최소/최대 면 중앙에 놓이며, 모든 실험점이 입력한 범위 안에 배치되는 CCD 계열 설계입니다.")
    if design_name == "Full factorial":
        st.warning("Full factorial + 중심점만으로는 제곱항 추정이 불안정할 수 있습니다. RSM 최적화 목적이면 CCF, CCD, Box-Behnken을 권장합니다.")

    design_preview = (
        design_df.drop(columns=RESPONSE_COLUMNS, errors="ignore")
        .sort_values("Run", kind="stable")
        .reset_index(drop=True)
    )
    factor_preview_columns = [
        column
        for factor in factors
        for column in (factor, f"{factor}_coded")
    ]
    preview_columns = [
        "Run",
        "Batch",
        "PointType",
        *factor_preview_columns,
    ]
    preview_labels = design_result_labels(
        factors,
        [],
        factor_codes=factor_codes,
        multiline=True,
    )
    print_notes = st.text_area(
        "인쇄 참고사항",
        key=f"design_print_notes_{input_nonce}",
        placeholder="시료 준비, 작업 조건, 주의사항 등을 입력하세요.",
        height=80,
        help="입력한 내용은 인쇄물의 요인 범위 옆 참고사항 칸에 표시됩니다. 비워 두면 손으로 적을 공간으로 인쇄됩니다.",
    )
    safe_design_name = design_name.lower().replace(" ", "_").replace("-", "_")
    download_col, print_col = st.columns(2)
    download_col.download_button(
        "실험계획 CSV 다운로드",
        data=make_design_csv(
            design_df,
            factors,
            active_responses,
            response_labels,
            factor_codes,
            blank_responses=True,
        ),
        file_name=f"rsm_{safe_design_name}_{factor_count}factor_batch{int(batch_count)}_seed{int(random_seed)}_plan.csv",
        mime="text/csv",
        width="stretch",
        key=f"design_plan_download_{input_nonce}_{safe_design_name}",
    )
    with print_col:
        render_design_print_button(
            design_preview,
            preview_columns,
            preview_labels,
            design_name,
            factor_count,
            display_ranges,
            int(center_points),
            int(batch_count),
            int(random_seed),
            print_notes,
        )
    st.caption(
        "설계표는 실제 수행할 실행순번대로 표시합니다. 같은 Batch의 실험은 연속해서 나오며, Batch 안의 실험점 순서는 seed로 랜덤화됩니다.",
        help=term_help("Run", "Batch", "Point type", "coded"),
    )
    st.dataframe(
        design_preview,
        width="stretch",
        hide_index=True,
        column_order=preview_columns,
        column_config={
            "Run": st.column_config.NumberColumn(
                "실행순번",
                help=term_help("Run"),
                format="%d",
            ),
            "Batch": st.column_config.NumberColumn(
                "배치번호",
                help=term_help("Batch"),
                format="%d",
            ),
            "PointType": st.column_config.TextColumn(
                "포인트타입",
                help=term_help("Point type"),
            ),
            **{
                factor: st.column_config.NumberColumn(preview_labels[factor])
                for factor in factors
            },
            **{
                f"{factor}_coded": st.column_config.NumberColumn(
                    preview_labels[f"{factor}_coded"],
                    help=term_help("coded"),
                )
                for factor in factors
            },
        },
    )
    return {
        "design_df": design_df,
        "design_name": design_name,
        "design_info": design_info,
        "factor_count": factor_count,
        "factors": factors,
        "factor_codes": factor_codes,
        "display_ranges": display_ranges,
        "center_points": center_points,
        "batch_count": batch_count,
        "random_seed": random_seed,
        "max_runs_per_batch": max_runs_per_batch,
        "safe_design_name": safe_design_name,
        "active_responses": active_responses,
    }
