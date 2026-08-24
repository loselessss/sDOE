from __future__ import annotations

import hashlib
import importlib

import numpy as np
import pandas as pd
import streamlit as st

from rsm_config import APP_BUILD_VERSION, term_help
from rsm_core import *
from rsm_design import *
from rsm_state import *
from rsm_table_component import DESIGN_RESPONSE_TABLE_COMPONENT


def mount_design_response_table_component(**kwargs: object) -> object:
    global DESIGN_RESPONSE_TABLE_COMPONENT
    try:
        return DESIGN_RESPONSE_TABLE_COMPONENT(**kwargs)
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        component_module = importlib.import_module("rsm_table_component")
        component_module = importlib.reload(component_module)
        DESIGN_RESPONSE_TABLE_COMPONENT = component_module.DESIGN_RESPONSE_TABLE_COMPONENT
        return DESIGN_RESPONSE_TABLE_COMPONENT(**kwargs)


def render_generated_result_input(
    context: dict[str, object],
    input_nonce: int,
    response_labels: dict[str, str],
) -> pd.DataFrame:
    design_df = context["design_df"]
    design_name = str(context["design_name"])
    factor_count = int(context["factor_count"])
    factors = list(context["factors"])
    factor_codes = dict(context["factor_codes"])
    display_ranges = dict(context["display_ranges"])
    center_points = int(context["center_points"])
    batch_count = int(context["batch_count"])
    random_seed = int(context["random_seed"])
    max_runs_per_batch = int(context["max_runs_per_batch"])
    safe_design_name = str(context["safe_design_name"])
    active_responses = list(context["active_responses"])
    base_input_df = (
        design_df.sort_values("Run", kind="stable")
        .reset_index(drop=True)
        .copy(deep=True)
    )
    design_input_df = base_input_df.copy(deep=True)
    range_signature = "_".join(f"{factor}:{display_ranges[factor][0]:.12g}:{display_ranges[factor][1]:.12g}" for factor in factors)
    reset_nonce = int(st.session_state.get("_input_reset_nonce", 0))
    editor_signature = (
        f"{design_name}_{factor_count}_{batch_count}_{center_points}_{random_seed}_"
        f"{max_runs_per_batch}_{'_'.join(factors)}_{range_signature}_{reset_nonce}"
    )
    safe_design_name = design_name.lower().replace(" ", "_").replace("-", "_")
    template_col, filled_col, upload_col = st.columns([1, 1, 1], vertical_alignment="center")
    template_col.download_button(
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
        key=f"design_plan_download_{editor_signature}",
    )
    with upload_col.popover(
        "실험표 업로드",
        icon=":material/upload_file:",
        help="실험계획 CSV에 결과값을 입력한 파일을 업로드합니다.",
        width="stretch",
    ):
        result_csv = st.file_uploader(
            "실험표 CSV 파일",
            type=["csv"],
            key=f"design_y_csv_upload_{editor_signature}",
            label_visibility="collapsed",
        )

    import_signature = ""
    if result_csv is not None:
        result_bytes = result_csv.getvalue()
        try:
            result_df = read_uploaded_table(result_bytes, result_csv.name, None)
            result_df = normalize_design_csv_columns(
                result_df,
                factors,
                active_responses,
                response_labels,
                factor_codes,
            )
            if "Run" in result_df.columns:
                result_df = result_df.sort_values("Run", kind="stable").reset_index(drop=True)
            required_columns = ["Run", "Batch", "PointType", *factors, *active_responses]
            missing_columns = [column for column in required_columns if column not in result_df.columns]
            identity_columns = ["Batch", "PointType", *factors]
            structure_matches = not missing_columns
            structure_detail = ""
            uploaded_runs: list[int] = []
            if structure_matches:
                run_numeric = pd.to_numeric(result_df["Run"], errors="coerce")
                rounded_run = run_numeric.round()
                if (
                    run_numeric.isna().any()
                    or not np.allclose(
                        run_numeric.to_numpy(dtype=float),
                        rounded_run.to_numpy(dtype=float),
                        rtol=0.0,
                        atol=1e-9,
                    )
                ):
                    structure_matches = False
                    structure_detail = " 실행순번에 숫자가 아닌 값 또는 정수가 아닌 값이 있습니다."
                else:
                    result_df = result_df.copy(deep=True)
                    result_df["Run"] = rounded_run.astype(int)
                    result_df = result_df.sort_values("Run", kind="stable").reset_index(drop=True)
                    uploaded_runs = result_df["Run"].tolist()
                    duplicated_orders = result_df.loc[
                        result_df["Run"].duplicated(), "Run"
                    ].tolist()
                    valid_runs = set(
                        pd.to_numeric(base_input_df["Run"], errors="coerce")
                        .round()
                        .astype(int)
                        .tolist()
                    )
                    unexpected_orders = sorted(set(uploaded_runs) - valid_runs)
                    if duplicated_orders:
                        structure_matches = False
                        structure_detail = (
                            " 중복 실행순번: "
                            + ", ".join(map(str, sorted(set(duplicated_orders))))
                        )
                    elif unexpected_orders:
                        structure_matches = False
                        structure_detail = (
                            " 현재 설계에 없는 실행순번: "
                            + ", ".join(map(str, unexpected_orders))
                        )
                    elif not uploaded_runs:
                        structure_matches = False
                        structure_detail = " CSV에 실험 행이 없습니다."

            if structure_matches:
                expected_by_order = base_input_df.set_index("Run")
                actual_by_order = result_df.set_index("Run")
                for column in identity_columns:
                    expected = expected_by_order.loc[uploaded_runs, column]
                    actual = actual_by_order.loc[uploaded_runs, column]
                    if pd.api.types.is_numeric_dtype(expected):
                        actual_numeric = pd.to_numeric(actual, errors="coerce")
                        matches = actual_numeric.notna().to_numpy() & np.isclose(
                            actual_numeric.to_numpy(dtype=float),
                            pd.to_numeric(expected, errors="coerce").to_numpy(dtype=float),
                            rtol=1e-8,
                            atol=1e-9,
                        )
                    else:
                        matches = np.asarray(
                            actual.fillna("").astype(str).str.strip().tolist()
                        ) == np.asarray(
                            expected.fillna("").astype(str).str.strip().tolist()
                        )
                    if not bool(np.all(matches)):
                        mismatch_position = int(np.flatnonzero(~matches)[0])
                        mismatch_order = uploaded_runs[mismatch_position]
                        structure_matches = False
                        structure_detail = (
                            f" 실행순번 {mismatch_order}의 "
                            f"{design_result_labels(factors, [], factor_codes=factor_codes).get(column, column)} 값이 현재 설계와 다릅니다."
                        )
                        break

            if not structure_matches:
                detail = f" 누락 열: {', '.join(missing_columns)}" if missing_columns else ""
                st.error(
                    "현재 실험설계와 CSV 양식이 일치하지 않습니다."
                    f"{detail}{structure_detail} "
                    "위의 '실험계획 CSV 다운로드' 파일에 Y값을 입력해서 다시 불러오세요."
                )
            else:
                invalid_responses: list[str] = []
                imported_count = 0
                for response in active_responses:
                    raw_response = result_df[response]
                    numeric_response = pd.to_numeric(raw_response, errors="coerce")
                    invalid_mask = raw_response.notna() & raw_response.astype(str).str.strip().ne("") & numeric_response.isna()
                    if invalid_mask.any():
                        invalid_responses.append(response)
                        continue
                    response_by_order = pd.Series(
                        numeric_response.to_numpy(),
                        index=uploaded_runs,
                    )
                    design_input_df[response] = (
                        pd.to_numeric(design_input_df["Run"], errors="coerce")
                        .round()
                        .astype(int)
                        .map(response_by_order)
                        .to_numpy()
                    )
                    response_count = int(numeric_response.notna().sum())
                    imported_count += response_count

                if invalid_responses:
                    st.error(f"{', '.join(invalid_responses)} 열에 숫자가 아닌 값이 있습니다. 실험계획 양식에 숫자 Y값만 입력해 주세요.")
                    design_input_df = base_input_df.copy(deep=True)
                else:
                    import_signature = hashlib.sha1(result_bytes).hexdigest()[:12]
                    missing_orders = sorted(
                        set(
                            pd.to_numeric(base_input_df["Run"], errors="coerce")
                            .round()
                            .astype(int)
                            .tolist()
                        )
                        - set(uploaded_runs)
                    )
                    if missing_orders:
                        st.warning(
                            "CSV에 없는 실행순번 "
                            + ", ".join(map(str, missing_orders))
                            + "은 결과값을 빈칸으로 남겼습니다."
                        )
                    st.success(f"실험표 CSV에서 결과값 {imported_count}개를 반영했습니다.")
        except Exception as exc:
            st.error(f"CSV를 읽을 수 없습니다: {exc} 위의 '실험계획 CSV 다운로드' 파일을 사용해 주세요.")

    input_refactor_version = f"{APP_BUILD_VERSION}_new_page_fresh_input_state"
    clear_design_input_state_once(input_refactor_version)
    design_state_token = hashlib.sha1(
        f"{editor_signature}_{input_refactor_version}_{import_signature}".encode("utf-8")
    ).hexdigest()[:12]

    st.caption(
        f"표의 {', '.join(active_responses)} 셀을 선택하고 엑셀 범위를 붙여넣으면 해당 셀부터 행·열 순서대로 바로 입력됩니다.",
        help=term_help("Run", "Batch", "Point type", "coded"),
    )
    response_edit_columns = active_responses.copy()
    table_columns = design_result_columns(factors, response_edit_columns)
    table_column_labels = design_result_labels(
        factors,
        response_edit_columns,
        response_labels,
        factor_codes,
        multiline=True,
    )
    integer_columns = {"Run", "Batch"}
    table_store_key = f"design_table_response_store_{design_state_token}"
    table_component_key = f"design_response_grid_{design_state_token}"
    saved_column_widths = component_state_value(table_component_key, "column_widths", {})
    if not isinstance(saved_column_widths, dict):
        saved_column_widths = {}
    table_payload = st.session_state.get(table_store_key, {})
    plain_response_df = response_frame_from_table_payload(
        table_payload,
        response_edit_columns,
        len(design_input_df),
    )
    plain_response_active = bool(plain_response_df.notna().any().any())
    if plain_response_active:
        design_input_df = apply_plain_response_to_design(
            design_input_df,
            plain_response_df,
            response_edit_columns,
        )
        value_count = int(plain_response_df.notna().sum().sum())
        st.success(
            f"표에서 입력한 Y값 {value_count}개를 반영했습니다."
        )
    if plain_response_active:
        completion_counts = {
            response: int(
                pd.to_numeric(design_input_df[response], errors="coerce").notna().sum()
            )
            for response in response_edit_columns
        }
        st.caption(
            "입력 현황: "
            + " · ".join(
                f"{response} {count}/{len(design_input_df)}"
                for response, count in completion_counts.items()
            )
        )
        incomplete_responses = {
            response: count
            for response, count in completion_counts.items()
            if 0 < count < len(design_input_df)
        }
        if incomplete_responses:
            incomplete_text = ", ".join(
                f"{response} {count}/{len(design_input_df)}"
                for response, count in incomplete_responses.items()
            )
            st.warning(
                f"현재 설계의 결과가 덜 입력되었습니다: {incomplete_text}. "
                "이 설계대로 남은 실험을 완료하거나, 다른 설계에서 얻은 결과라면 "
                "페이지 위의 '기존 실험결과 CSV 업로드'에 X값과 Y값을 함께 넣어 주세요."
            )
    filled_col.download_button(
        "입력한 실험표 CSV 다운로드",
        data=make_design_csv(
            design_input_df,
            factors,
            response_edit_columns,
            response_labels,
            factor_codes,
            blank_responses=False,
        ),
        file_name=f"rsm_{safe_design_name}_{factor_count}factor_batch{int(batch_count)}_seed{int(random_seed)}_filled.csv",
        mime="text/csv",
        width="stretch",
        key=f"filled_design_download_{design_state_token}",
    )
    design_column_config = {}
    for column in table_columns:
        if column in response_edit_columns:
            design_column_config[column] = st.column_config.NumberColumn(
                table_column_labels[column],
                help="결과값을 붙여넣거나 직접 입력하세요.",
                format="%.4f",
            )
        elif column == "PointType":
            design_column_config[column] = st.column_config.TextColumn(
                table_column_labels[column],
                help=term_help("Point type"),
            )
        elif column.endswith("_coded"):
            design_column_config[column] = st.column_config.NumberColumn(
                table_column_labels[column],
                help=term_help("coded"),
            )
        elif column in integer_columns:
            design_column_config[column] = st.column_config.NumberColumn(
                table_column_labels[column],
                format="%d",
            )
        else:
            design_column_config[column] = st.column_config.NumberColumn(table_column_labels[column])

    if DESIGN_RESPONSE_TABLE_COMPONENT is not None:
        component_rows = (
            design_input_df.loc[:, table_columns].astype(object)
            .where(pd.notna(design_input_df.loc[:, table_columns]), None)
            .to_dict(orient="records")
        )
        mount_design_response_table_component(
            data={
                "rows": component_rows,
                "columns": table_columns,
                "editable_columns": response_edit_columns,
                "integer_columns": sorted(integer_columns),
                "column_widths": saved_column_widths,
                "column_labels": table_column_labels,
            },
            key=table_component_key,
            on_edit_change=lambda: capture_design_table_edit(table_component_key, table_store_key),
            on_column_widths_change=lambda: None,
            width="stretch",
            height=min(520, max(180, 44 + len(design_input_df) * 35)),
        )
    else:
        st.error("현재 Streamlit 버전에서는 표 직접 붙여넣기 구성요소를 사용할 수 없습니다.")
        st.dataframe(
            design_input_df.loc[:, table_columns],
            width="stretch",
            hide_index=True,
            column_order=table_columns,
            column_config=design_column_config,
        )
    return design_input_df
