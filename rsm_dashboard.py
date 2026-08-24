from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from rsm_3d import *
from rsm_config import term_help
from rsm_core import *
from rsm_design import *
from rsm_export import *
from rsm_plots import *
from rsm_statistics import *


def render_rsm_dashboard(
    source_df: pd.DataFrame,
    factors: list[str],
    response_columns: list[str],
    key_prefix: str,
    design_info: tuple[str, str] | None = None,
    response_labels: dict[str, str] | None = None,
) -> None:
    if not response_columns:
        st.info("사용 중인 Y열에 값을 입력하면 바로 RSM 분석이 표시됩니다.")
        return

    display_labels = response_labels or {}
    controls = st.columns([1, 1, 1])
    response_name = controls[0].radio(
        "반응값",
        response_columns,
        horizontal=True,
        format_func=lambda name: display_labels.get(name, name),
        key=f"{key_prefix}_response",
        help="그래프와 통계표에서 분석할 Y 반응값을 선택합니다.",
    )
    plot_axes = controls[1].multiselect(
        "Contour 축",
        factors,
        default=factors[:2],
        max_selections=2,
        key=f"{key_prefix}_axes",
        help=term_help("Contour"),
    )
    grid_size = controls[2].slider(
        "그림 해상도",
        30,
        120,
        60,
        10,
        key=f"{key_prefix}_grid",
        help="Contour와 3D Surface를 계산할 격자 수입니다. 높을수록 부드럽지만 계산량이 늘어납니다.",
    )

    if len(plot_axes) != 2:
        st.warning("Contour 축을 정확히 2개 선택하세요.")
        return

    model_df, dropped_rows = clean_numeric_data(source_df, factors + [response_name])
    if dropped_rows > 0:
        st.warning(f"숫자로 변환할 수 없거나 비어 있는 행 {dropped_rows}개를 제외했습니다.")

    param_count = len(build_terms(len(factors)))
    if len(model_df) < param_count:
        st.info(f"현재 유효 행 {len(model_df)}개입니다. {len(factors)}요인 full quadratic 모델에는 최소 {param_count}개가 필요합니다.")
        return

    result = fit_quadratic_model(
        model_df,
        factors,
        response_name,
        display_labels.get(response_name, response_name),
    )
    stationary = compute_stationary_point(result)
    design_label, design_note = design_info or detect_design_type(model_df, factors)

    if result.rank < param_count:
        st.warning("설계행렬의 rank가 부족합니다. 일부 계수가 독립적으로 추정되지 않을 수 있습니다.")
    elif result.condition_number > 1e8:
        st.warning("설계행렬의 조건수가 매우 큽니다. 계수와 정상점이 작은 데이터 변화에 민감할 수 있습니다.")

    fixed_values: dict[str, float] = {}
    fixed_factors = [factor for factor in factors if factor not in plot_axes]
    if fixed_factors:
        fixed_cols = st.columns(len(fixed_factors))
        for idx, factor in enumerate(fixed_factors):
            min_val = float(model_df[factor].min())
            max_val = float(model_df[factor].max())
            mean_val = float(model_df[factor].mean())
            with fixed_cols[idx]:
                if min_val == max_val:
                    fixed_values[factor] = min_val
                    st.number_input(
                        f"{factor} 고정값",
                        value=min_val,
                        disabled=True,
                        key=f"{key_prefix}_{factor}_fixed",
                        help="그래프 축으로 선택하지 않은 요인을 이 값으로 고정합니다.",
                    )
                else:
                    fixed_values[factor] = st.slider(
                        f"{factor} 고정값",
                        min_value=min_val,
                        max_value=max_val,
                        value=min(max(mean_val, min_val), max_val),
                        key=f"{key_prefix}_{factor}_fixed",
                        help="그래프 축으로 선택하지 않은 요인을 이 값으로 고정합니다.",
                    )

    summary_cols = st.columns(4)
    summary_cols[0].metric("유효 행", f"{len(model_df):,}", help=term_help("유효 행"))
    summary_cols[1].metric("설계 추정", design_label, help=term_help("설계 추정"))
    summary_cols[2].metric("R²", format_number(result.r2, 5), help=term_help("R²"))
    summary_cols[3].metric("Adjusted R²", format_number(result.adj_r2, 5), help=term_help("Adjusted R²"))
    st.caption(design_note)

    contour_tab, surface_tab, profiler_tab, predicted_tab, anova_tab, model_tab = st.tabs(
        ["Contour", "3D Surface", "Contour Profiler", "Predicted Plot", "ANOVA", "모델/정상점"]
    )

    with contour_tab:
        st.caption(
            "두 요인의 조합에 따른 예측 반응값을 등고선으로 표시합니다. 3요인 설계에서는 선택하지 않은 요인을 위에서 지정한 값으로 고정합니다.",
            help=term_help("Contour"),
        )
        contour_fig = make_contour_figure(result, model_df, stationary, plot_axes[0], plot_axes[1], fixed_values, grid_size)
        st.plotly_chart(
            contour_fig,
            width="stretch",
            key=f"{key_prefix}_contour_chart_{response_name}_{plot_axes[0]}_{plot_axes[1]}",
            config=plotly_chart_config(f"rsm_contour_{response_name}_{plot_axes[0]}_{plot_axes[1]}"),
        )
        st.download_button(
            "Contour 그래프 HTML 저장",
            data=contour_fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
            file_name=f"rsm_contour_{response_name}_{plot_axes[0]}_{plot_axes[1]}.html",
            mime="text/html",
            key=f"{key_prefix}_contour_html_{response_name}_{plot_axes[0]}_{plot_axes[1]}",
        )

    with surface_tab:
        st.caption(
            "Contour와 같은 예측면을 회전 가능한 3D로 확인합니다. 곡률과 최대점·최소점·안장점의 형태를 살펴보고 HTML·GLB로 저장할 수 있습니다.",
            help=term_help("3D Surface", "정상점"),
        )
        surface_fig = make_surface_figure(result, model_df, stationary, plot_axes[0], plot_axes[1], fixed_values, grid_size)
        st.plotly_chart(
            surface_fig,
            width="stretch",
            key=f"{key_prefix}_surface_chart_{response_name}_{plot_axes[0]}_{plot_axes[1]}",
            config=plotly_chart_config(f"rsm_3d_surface_{response_name}_{plot_axes[0]}_{plot_axes[1]}"),
        )
        st.download_button(
            "3D Surface 그래프 HTML 저장",
            data=surface_fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
            file_name=f"rsm_surface_{response_name}_{plot_axes[0]}_{plot_axes[1]}.html",
            mime="text/html",
            key=f"{key_prefix}_surface_html_{response_name}_{plot_axes[0]}_{plot_axes[1]}",
        )
        st.download_button(
            "PowerPoint용 GLB + 3D 범례 저장",
            data=make_surface_glb(result, plot_axes[0], plot_axes[1], fixed_values, min(grid_size, 80)),
            file_name=f"rsm_surface_{response_name}_{plot_axes[0]}_{plot_axes[1]}.glb",
            mime="model/gltf-binary",
            key=f"{key_prefix}_surface_glb_{response_name}_{plot_axes[0]}_{plot_axes[1]}",
            help="단일 GLB 파일 안에 표면 색상과 숫자 범례가 함께 들어가며 PowerPoint에서 같이 회전합니다.",
        )

    with profiler_tab:
        st.caption(
            "각 요인의 현재값을 움직여 예측 반응과 desirability 변화를 실시간으로 확인합니다. 목표값과 허용범위는 최적 조건 탐색 기준으로 사용됩니다.",
            help=term_help("Prediction Profiler", "Contour Profiler", "Desirability"),
        )
        y_min = float(model_df[response_name].min())
        y_max = float(model_df[response_name].max())
        y_mean = float(model_df[response_name].mean())
        default_span = max((y_max - y_min) * 0.2, 1.0)
        limit_cols = st.columns([1, 1, 1])
        target_value = limit_cols[0].number_input(
            "Target",
            value=float(y_mean),
            key=f"{key_prefix}_profiler_target",
            help="가장 바람직하다고 설정할 목표 반응값입니다.",
        )
        low_limit = limit_cols[1].number_input(
            "Lo Limit",
            value=float(y_mean - default_span),
            key=f"{key_prefix}_profiler_low",
            help="허용할 반응값의 하한입니다. 이 값 이하는 desirability가 0입니다.",
        )
        high_limit = limit_cols[2].number_input(
            "Hi Limit",
            value=float(y_mean + default_span),
            key=f"{key_prefix}_profiler_high",
            help="허용할 반응값의 상한입니다. 이 값 이상은 desirability가 0입니다.",
        )
        if not (low_limit < target_value < high_limit):
            st.warning("Lo Limit < Target < Hi Limit 순서가 되도록 입력하세요.")

        current_values: dict[str, float] = {}
        for idx, factor in enumerate(factors):
            min_val = float(model_df[factor].min())
            max_val = float(model_df[factor].max())
            default_value = float(stationary.point[idx]) if stationary.point is not None and np.isfinite(stationary.point[idx]) else float(model_df[factor].mean())
            current_values[factor] = min(max(default_value, min_val), max_val)

        current_point = np.asarray([current_values[factor] for factor in factors], dtype=float)
        current_y = predict_single(result, current_point)
        current_d = float(desirability_values(np.asarray([current_y]), low_limit, target_value, high_limit)[0])
        live_factor = st.selectbox(
            "Prediction Profiler 실시간 조정 요인",
            factors,
            index=0,
            key=f"{key_prefix}_prediction_live_factor",
            help=term_help("Prediction Profiler"),
        )
        remembered = pd.DataFrame(
            [
                {
                    "Setting": "_Current_",
                    **{factor: current_values[factor] for factor in factors},
                    response_name: current_y,
                    "Lo Limit": low_limit,
                    "Hi Limit": high_limit,
                    "Desirability": current_d,
                }
            ]
        )
        st.subheader("Prediction Profiler")
        prediction_profiler_fig = make_prediction_profiler_figure(
            result,
            model_df,
            current_values,
            low_limit,
            target_value,
            high_limit,
            live_factor=live_factor,
        )
        st.plotly_chart(
            prediction_profiler_fig,
            width="stretch",
            key=f"{key_prefix}_jmp_prediction_profiler_{response_name}_{live_factor}",
            config=plotly_chart_config(f"rsm_prediction_profiler_{response_name}"),
        )
        st.download_button(
            "Prediction Profiler HTML 저장",
            data=prediction_profiler_fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
            file_name=f"rsm_prediction_profiler_{response_name}.html",
            mime="text/html",
            key=f"{key_prefix}_prediction_profiler_html_{response_name}_{live_factor}",
        )
        st.subheader("Remembered Settings")
        st.dataframe(
            remembered.style.format({col: "{:.4f}" for col in remembered.columns if col != "Setting"}),
            width="stretch",
            hide_index=True,
        )

        st.subheader("Contour Profiler")
        contour_meta = st.columns([1, 1, 1, 1])
        default_profiler_axes = plot_axes if len(plot_axes) == 2 else factors[:2]
        profiler_axis_x = contour_meta[0].selectbox(
            "Contour X축",
            factors,
            index=default_index(factors, default_profiler_axes[0]),
            key=f"{key_prefix}_profiler_axis_x",
            help=term_help("Contour Profiler"),
        )
        profiler_y_options = [factor for factor in factors if factor != profiler_axis_x]
        profiler_axis_y = contour_meta[1].selectbox(
            "Contour Y축",
            profiler_y_options,
            index=default_index(profiler_y_options, default_profiler_axes[1] if default_profiler_axes[1] != profiler_axis_x else profiler_y_options[0]),
            key=f"{key_prefix}_profiler_axis_y",
            help=term_help("Contour Profiler"),
        )
        contour_meta[2].metric(
            "Current Y",
            format_number(current_y, 6),
            help="현재 요인 설정에서 모델이 예측한 반응값입니다.",
        )
        contour_meta[3].metric(
            "Desirability",
            format_number(current_d, 5),
            help=term_help("Desirability"),
        )
        profiler_fixed_factors = [factor for factor in factors if factor not in [profiler_axis_x, profiler_axis_y]]
        profiler_fixed_values = {factor: current_values[factor] for factor in profiler_fixed_factors}
        control_table = pd.DataFrame(
            {
                "Factor": factors,
                "Current X": [current_values[factor] for factor in factors],
            }
        )
        st.dataframe(control_table.style.format({"Current X": "{:.4f}"}), width="stretch", hide_index=True)
        contour_profiler_fig = make_jmp_style_contour_figure(
            result,
            model_df,
            stationary,
            profiler_axis_x,
            profiler_axis_y,
            profiler_fixed_values,
            current_values,
            low_limit,
            target_value,
            high_limit,
            grid_size,
        )
        st.plotly_chart(
            contour_profiler_fig,
            width="stretch",
            key=f"{key_prefix}_jmp_contour_profiler_{response_name}_{profiler_axis_x}_{profiler_axis_y}",
            config=plotly_chart_config(
                f"rsm_contour_profiler_{response_name}_{profiler_axis_x}_{profiler_axis_y}"
            ),
        )
        st.download_button(
            "Contour Profiler HTML 저장",
            data=contour_profiler_fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
            file_name=f"rsm_contour_profiler_{response_name}_{profiler_axis_x}_{profiler_axis_y}.html",
            mime="text/html",
            key=f"{key_prefix}_contour_profiler_html_{response_name}_{profiler_axis_x}_{profiler_axis_y}",
        )

    with predicted_tab:
        st.caption(
            "실측값과 모델 예측값의 일치도를 비교하고 잔차 분포를 확인합니다. 점들이 기준선에서 체계적으로 벗어나면 모델 또는 이상치를 점검하세요.",
            help=term_help("Predicted Plot"),
        )
        predicted_fig = make_prediction_diagnostic_figure(result, model_df)
        st.plotly_chart(
            predicted_fig,
            width="stretch",
            key=f"{key_prefix}_predicted_chart_{response_name}",
            config=plotly_chart_config(f"rsm_predicted_plot_{response_name}"),
        )
        st.download_button(
            "Predicted Plot HTML 저장",
            data=predicted_fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
            file_name=f"rsm_predicted_plot_{response_name}.html",
            mime="text/html",
            key=f"{key_prefix}_predicted_html_{response_name}",
        )

    with anova_tab:
        anova, lack_of_fit, lack_message = make_anova_tables(result, model_df)
        st.caption(
            "ANOVA로 quadratic 모델 전체의 통계적 유의성을 확인합니다. 동일 조건 반복점이 있으면 순수오차와 lack of fit을 분리해 모델 부족 여부도 검정합니다.",
            help=term_help("ANOVA", "Lack of fit"),
        )
        st.dataframe(
            anova.style.format({"SS": "{:.4f}", "MS": "{:.4f}", "F": "{:.4f}", "p-value": "{:.4f}"}),
            width="stretch",
            hide_index=True,
        )
        st.subheader("Lack of fit", help=term_help("Lack of fit"))
        st.caption(lack_message)
        if lack_of_fit is None:
            st.info("Lack of fit 표를 만들 수 없습니다.")
        else:
            st.dataframe(
                lack_of_fit.style.format({"SS": "{:.4f}", "MS": "{:.4f}", "F": "{:.4f}", "p-value": "{:.4f}"}),
                width="stretch",
                hide_index=True,
            )

    with model_tab:
        st.caption(
            "적합된 2차 회귀식과 항별 계수를 확인합니다. gradient=0으로 계산한 정상점은 Hessian 고유값으로 최대·최소·안장점을 분류하며 실험범위 밖이면 경고합니다.",
            help=term_help("정상점", "Hessian"),
        )
        st.subheader("모델 식")
        st.code(equation_text(result), language="text")
        details_left, details_right = st.columns([1, 1])
        with details_left:
            st.subheader("계수")
            st.dataframe(
                coefficient_table(result).style.format({"계수": "{:.4f}"}),
                width="stretch",
                hide_index=True,
            )
        with details_right:
            st.subheader("정상점", help=term_help("정상점", "Hessian"))
            st.write(stationary.message)
            st.write(f"분류: **{stationary.classification}**")
            st.dataframe(
                pd.DataFrame({"Hessian 고유값": stationary.eigenvalues}).style.format("{:.4f}"),
                width="stretch",
                hide_index=True,
            )
            if stationary.point is not None:
                point_df = pd.DataFrame(
                    {
                        "요인": factors,
                        "정상점 값": stationary.point,
                        "실험 최소": [result.x_min[factor] for factor in factors],
                        "실험 최대": [result.x_max[factor] for factor in factors],
                    }
                )
                point_df["범위 내"] = (
                    (point_df["정상점 값"] >= point_df["실험 최소"])
                    & (point_df["정상점 값"] <= point_df["실험 최대"])
                )
                st.dataframe(
                    point_df.style.format({"정상점 값": "{:.4f}", "실험 최소": "{:.4f}", "실험 최대": "{:.4f}"}),
                    width="stretch",
                    hide_index=True,
                )
                if not bool(point_df["범위 내"].all()):
                    st.warning("정상점이 실험 범위 밖에 있습니다. 외삽 영역의 예측값이므로 해석에 주의하세요.")
                st.metric(
                    "정상점 예측 반응값",
                    format_number(predict_single(result, stationary.point), 6),
                    help=term_help("정상점"),
                )

        with st.expander("적합값과 잔차"):
            residual_df = model_df.copy()
            residual_df["fitted"] = result.y_hat
            residual_df["residual"] = result.residuals
            st.dataframe(residual_df, width="stretch")

    st.divider()
    st.caption("아래 Excel은 각 탭의 계산 데이터를 시트별로 저장합니다. 다운로드 위치는 브라우저 또는 EXE 내부 브라우저의 다운로드 설정을 따릅니다.")
    st.download_button(
        "RSM 결과 전체 Excel 저장",
        data=make_rsm_result_excel_file(
            source_df,
            model_df,
            result,
            stationary,
            design_label,
            design_note,
            plot_axes,
            fixed_values,
            grid_size,
            profiler_axis_x,
            profiler_axis_y,
            profiler_fixed_values,
            current_values,
            low_limit,
            target_value,
            high_limit,
            anova,
            lack_of_fit,
        ),
        file_name=f"rsm_results_{response_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        key=f"{key_prefix}_rsm_results_xlsx_{response_name}_{plot_axes[0]}_{plot_axes[1]}",
    )



