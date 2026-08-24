"""
Interactive RSM analysis app for DOE data.

Run:
    streamlit run rsm_streamlit_app.py

Required packages:
    streamlit pandas numpy plotly openpyxl
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


REQUIRED_PACKAGES = {
    "streamlit": "streamlit",
    "pandas": "pandas",
    "numpy": "numpy",
    "plotly": "plotly",
    "openpyxl": "openpyxl",
}

from rsm_config import RESPONSE_COLUMNS, term_help


def missing_packages() -> list[str]:
    return [
        package_name
        for import_name, package_name in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(import_name) is None
    ]


def running_inside_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def ensure_streamlit_launcher() -> None:
    missing = missing_packages()
    if missing:
        print("\n[DOE RSM 앱] 필요한 파이썬 패키지가 설치되어 있지 않습니다.")
        print("아래 명령을 터미널/명령 프롬프트에서 한 번 실행한 뒤 다시 실행하세요:\n")
        print(f"{sys.executable} -m pip install {' '.join(missing)}")
        print("\n설치 후 실행:")
        print(f"{sys.executable} {Path(__file__).name}\n")
        raise SystemExit(1)

    if not running_inside_streamlit():
        from streamlit.web import cli as streamlit_cli

        sys.argv = [
            "streamlit",
            "run",
            str(Path(__file__).resolve()),
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ]
        raise SystemExit(streamlit_cli.main())


if os.environ.get("RSM_APP_NO_AUTO_LAUNCH") != "1":
    ensure_streamlit_launcher()

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="DOE RSM 분석",
    page_icon=str(Path(__file__).resolve().parent / "assets" / "rsm_icon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)


from rsm_core import normalize_name, read_uploaded_table
from rsm_dashboard import render_rsm_dashboard
from rsm_design import infer_external_analysis_columns, valid_response_columns
from rsm_design_ui import build_generated_design
from rsm_result_ui import render_generated_result_input
from rsm_state import initialize_input_session_nonce, reset_input_state

initialize_input_session_nonce()

st.title("DOE 실험설계 + RSM 분석 앱")
st.caption(
    "실험표를 만들거나 CSV/XLSX를 업로드한 뒤, Y 값을 입력하면 바로 RSM, contour, profiler를 확인합니다.",
    help=term_help("RSM", "Contour", "Prediction Profiler"),
)
st.info("다운로드 버튼을 누른 파일은 앱 폴더가 아니라 브라우저의 기본 다운로드 폴더에 저장됩니다. 보통 Windows의 '다운로드' 폴더이며, 브라우저 설정에 따라 위치가 달라질 수 있습니다.")
st.button(
    "입력 초기화",
    key="reset_input_button",
    help="업로드 파일, 붙여넣기 내용, 컬럼 매핑, 설계표 입력값을 비우고 처음 상태로 돌아갑니다.",
    on_click=reset_input_state,
)
input_nonce = int(st.session_state.get("_input_reset_nonce", 0))

external_analysis_context: dict[str, object] | None = None
external_result_file = st.file_uploader(
    "기존 실험결과 CSV 업로드",
    type=["csv"],
    key=f"external_analysis_upload_{input_nonce}",
    help="앞에서 만든 설계와 실험 건수를 무시하고 CSV의 X·Y 열을 판별해 바로 분석합니다.",
)
if external_result_file is not None:
    try:
        external_bytes = external_result_file.getvalue()
        external_df = read_uploaded_table(
            external_bytes,
            external_result_file.name,
            None,
        )
        external_df = external_df.rename(
            columns={column: str(column).strip() for column in external_df.columns}
        )
        inferred_columns = infer_external_analysis_columns(external_df)
        external_signature = hashlib.sha1(external_bytes).hexdigest()[:12]
        factor_defaults = list(inferred_columns["factor_columns"])
        numeric_options = list(inferred_columns["numeric_columns"])
        with st.expander("열 인식 확인", expanded=False):
            selected_external_factors = st.multiselect(
                "X 요인 열",
                numeric_options,
                default=factor_defaults,
                max_selections=3,
                key=f"external_factors_{external_signature}",
                help="앱이 자동 판별한 2개 또는 3개의 요인 열입니다.",
            )
            response_options = [
                column
                for column in numeric_options
                if column not in selected_external_factors
            ]
            response_defaults = [
                column
                for column in inferred_columns["response_columns"]
                if column in response_options
            ][: len(RESPONSE_COLUMNS)]
            selected_external_responses = st.multiselect(
                "Y 결과 열",
                response_options,
                default=response_defaults,
                max_selections=len(RESPONSE_COLUMNS),
                key=f"external_responses_{external_signature}",
                help=f"분석할 결과 열입니다. 최대 Y{len(RESPONSE_COLUMNS)}까지 선택할 수 있습니다.",
            )

        if len(selected_external_factors) not in {2, 3}:
            st.error("X 요인 열은 2개 또는 3개를 선택해야 합니다.")
        elif not selected_external_responses:
            st.error("Y 결과 열을 하나 이상 선택해야 합니다.")
        else:
            external_analysis_context = {
                "data": external_df,
                "factors": list(selected_external_factors),
                "responses": list(selected_external_responses),
                "response_labels": {
                    response: response for response in selected_external_responses
                },
                "signature": external_signature,
                "file_name": external_result_file.name,
            }
            st.success(
                f"{len(selected_external_factors)}요인으로 인식했습니다: "
                + ", ".join(selected_external_factors)
            )
            st.caption(
                f"외부 CSV의 {len(external_df)}개 행을 사용합니다. "
                "앞에서 만든 설계의 실험 건수와는 비교하지 않습니다."
            )
    except Exception as exc:
        st.error(f"외부 실험결과 CSV를 읽을 수 없습니다: {exc}")

response_labels: dict[str, str] = {response: response for response in RESPONSE_COLUMNS}
if external_analysis_context is None:
    response_header, response_count_control = st.columns([2, 1], vertical_alignment="bottom")
    response_header.markdown("**반응값 이름**")
    response_count = int(
        response_count_control.number_input(
            "반응값 수",
            min_value=1,
            max_value=len(RESPONSE_COLUMNS),
            value=3,
            step=1,
            key=f"response_count_{input_nonce}",
            help="분석할 Y 반응값 열의 개수입니다. Y1부터 Y6까지 사용할 수 있습니다.",
        )
    )
    active_response_columns = RESPONSE_COLUMNS[:response_count]
    for row_start in range(0, response_count, 3):
        row_responses = active_response_columns[row_start : row_start + 3]
        response_name_cols = st.columns(3)
        for column, response in zip(response_name_cols, row_responses):
            entered_name = column.text_input(
                f"{response} 이름",
                value=response,
                key=f"response_name_{response}_{input_nonce}",
            ).strip()
            response_labels[response] = entered_name or response

    normalized_response_labels = [normalize_name(response_labels[response]) for response in active_response_columns]
    if len(normalized_response_labels) != len(set(normalized_response_labels)):
        st.error("사용 중인 반응값 이름은 서로 달라야 합니다.")
        st.stop()
else:
    active_response_columns = []
    normalized_response_labels = []

has_entered_results = external_analysis_context is not None
default_workflow_tab = "분석" if has_entered_results else "설계"
design_tab, result_input_tab, analysis_tab = st.tabs(
    ["설계", "결과입력", "분석"],
    default=default_workflow_tab,
    key=f"workflow_tabs_{input_nonce}_{default_workflow_tab}",
)
st.html(
    """
    <style>
    div[class*="st-key-workflow_tabs_"] [role="tablist"] > [role="tab"] {
        min-height: 52px !important;
        padding: 12px 30px !important;
    }
    div[class*="st-key-workflow_tabs_"] [role="tablist"] > [role="tab"] p {
        font-size: 18px !important;
        font-weight: 650 !important;
    }
    div[class*="st-key-workflow_tabs_"] [role="tabpanel"] [role="tablist"] > [role="tab"] {
        min-height: 40px !important;
        padding: 8px 16px !important;
    }
    div[class*="st-key-workflow_tabs_"] [role="tabpanel"] [role="tablist"] > [role="tab"] p {
        font-size: 14px !important;
        font-weight: 400 !important;
    }
    </style>
    """
)

generated_context: dict[str, object] | None = None
generated_results: pd.DataFrame | None = None

with design_tab:
    if external_analysis_context is not None:
        st.info("외부 실험결과 CSV를 사용 중입니다. 앞에서 만든 실험설계는 이번 분석에 사용하지 않습니다.")
    else:
        generated_context = build_generated_design(
            input_nonce,
            normalized_response_labels,
            active_response_columns,
            response_labels,
        )
with result_input_tab:
    if external_analysis_context is not None:
        external_factors = list(external_analysis_context["factors"])
        external_responses = list(external_analysis_context["responses"])
        st.caption(
            "업로드한 파일에서 자동 인식한 X·Y 열입니다. 열 선택을 바꾸려면 위의 '열 인식 확인'을 여세요."
        )
        st.dataframe(
            external_analysis_context["data"].loc[
                :, [*external_factors, *external_responses]
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption(
            f"새로 만든 설계의 결과를 입력하는 단계입니다. 표의 {', '.join(active_response_columns)}에 직접 입력·붙여넣거나, 실험계획 CSV에 결과값을 채워 업로드하세요.",
            help=term_help("Run", "Batch", "Point type", "coded"),
        )
        generated_results = render_generated_result_input(generated_context, input_nonce, response_labels)

with analysis_tab:
    st.subheader("RSM 결과", help=term_help("RSM"))
    st.caption(
        "유효한 X·Y 행으로 full quadratic RSM을 적합합니다. 반응값과 표시 축을 선택한 뒤 Contour, 3D Surface, Profiler, 예측 진단, ANOVA와 정상점을 확인하세요.",
        help=term_help("RSM", "Contour", "3D Surface", "Predicted Plot", "ANOVA", "정상점"),
    )
    if external_analysis_context is not None:
        external_data = external_analysis_context["data"]
        external_factors = list(external_analysis_context["factors"])
        external_responses = valid_response_columns(
            external_data,
            external_factors,
            list(external_analysis_context["responses"]),
        )
        if external_responses:
            render_rsm_dashboard(
                external_data,
                external_factors,
                external_responses,
                f"external_{external_analysis_context['signature']}",
                response_labels=dict(external_analysis_context["response_labels"]),
            )
        else:
            st.info("업로드한 CSV에서 분석 가능한 숫자 Y값을 찾지 못했습니다.")
    elif generated_context is not None and generated_results is not None:
        generated_factors = list(generated_context["factors"])
        generated_responses = valid_response_columns(
            generated_results,
            generated_factors,
            list(generated_context["active_responses"]),
        )
        if generated_responses:
            render_rsm_dashboard(
                generated_results,
                generated_factors,
                generated_responses,
                f"design_{input_nonce}",
                design_info=generated_context["design_info"],
                response_labels=response_labels,
            )
        else:
            st.info("결과입력 탭에서 Y값을 입력하면 이 탭에 RSM 분석 결과가 표시됩니다.")
