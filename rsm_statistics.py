from __future__ import annotations

import math

import numpy as np
import pandas as pd

from rsm_core import *


def predict_single(result: FitResult, point: np.ndarray) -> float:
    prediction = design_matrix(point.reshape(1, -1), result.terms) @ result.beta
    return float(prediction.item())


def format_number(value: float, digits: int = 5) -> str:
    if not np.isfinite(value):
        return "NA"
    return f"{value:.{digits}g}"


def plotly_chart_config(file_name: str) -> dict[str, object]:
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": file_name,
            "scale": 2,
        },
    }


def _beta_continued_fraction(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-14) -> float:
    tiny = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_beta(x: float, a: float, b: float) -> float:
    if not (0.0 <= x <= 1.0) or a <= 0 or b <= 0:
        return np.nan
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _beta_continued_fraction(a, b, x) / a
    return 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x) / b


def f_survival(f_value: float, df1: float, df2: float) -> float:
    if not np.isfinite(f_value) or f_value < 0 or df1 <= 0 or df2 <= 0:
        return np.nan
    x = (df1 * f_value) / (df1 * f_value + df2)
    cdf = regularized_beta(x, df1 / 2.0, df2 / 2.0)
    if not np.isfinite(cdf):
        return np.nan
    return max(0.0, min(1.0, 1.0 - cdf))


def make_anova_tables(result: FitResult, data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None, str]:
    y = data[result.y_name].to_numpy(dtype=float)
    n = len(y)
    ss_res = float(np.sum(result.residuals**2))
    ss_total = float(np.sum((y - np.mean(y)) ** 2))
    ss_model = max(0.0, ss_total - ss_res)
    df_model = max(result.rank - 1, 0)
    df_residual = n - result.rank
    df_total = n - 1
    ms_model = ss_model / df_model if df_model > 0 else np.nan
    ms_residual = ss_res / df_residual if df_residual > 0 else np.nan
    f_model = ms_model / ms_residual if np.isfinite(ms_model) and np.isfinite(ms_residual) and ms_residual > 0 else np.nan
    p_model = f_survival(f_model, df_model, df_residual)

    anova = pd.DataFrame(
        {
            "Source": ["Model", "Residual", "Total"],
            "DF": [df_model, df_residual, df_total],
            "SS": [ss_model, ss_res, ss_total],
            "MS": [ms_model, ms_residual, np.nan],
            "F": [f_model, np.nan, np.nan],
            "p-value": [p_model, np.nan, np.nan],
        }
    )

    grouped = data.groupby(result.factors, dropna=False)[result.y_name]
    group_count = grouped.ngroups
    pure_error_ss = float(grouped.apply(lambda values: np.sum((values - values.mean()) ** 2)).sum())
    pure_error_df = n - group_count
    lof_ss = max(0.0, ss_res - pure_error_ss)
    lof_df = df_residual - pure_error_df

    if pure_error_df <= 0:
        return anova, None, "반복 실험점이 없어 pure error를 계산할 수 없습니다. Lack of fit 검정은 반복점이 있을 때 가능합니다."
    if lof_df <= 0:
        return anova, None, "반복점은 있지만 lack of fit 자유도가 부족합니다. 중심점 외에도 설계 전체의 반복점이 더 필요할 수 있습니다."

    ms_lof = lof_ss / lof_df
    ms_pe = pure_error_ss / pure_error_df
    f_lof = ms_lof / ms_pe if ms_pe > 0 else np.nan
    p_lof = f_survival(f_lof, lof_df, pure_error_df)
    lack_of_fit = pd.DataFrame(
        {
            "Source": ["Lack of fit", "Pure error"],
            "DF": [lof_df, pure_error_df],
            "SS": [lof_ss, pure_error_ss],
            "MS": [ms_lof, ms_pe],
            "F": [f_lof, np.nan],
            "p-value": [p_lof, np.nan],
        }
    )
    return anova, lack_of_fit, "Lack of fit p-value가 작으면 현재 quadratic 모델이 데이터 형태를 충분히 설명하지 못할 가능성이 있습니다."


def equation_text(result: FitResult) -> str:
    pieces = [format_number(result.beta[0], 6)]
    for beta, (_, idxs) in zip(result.beta[1:], result.terms[1:]):
        if len(idxs) == 1:
            label = result.factors[idxs[0]]
        elif idxs[0] == idxs[1]:
            label = f"{result.factors[idxs[0]]}^2"
        else:
            label = f"{result.factors[idxs[0]]}*{result.factors[idxs[1]]}"
        sign = "+" if beta >= 0 else "-"
        pieces.append(f" {sign} {format_number(abs(beta), 6)}*{label}")
    return f"{result.y_label} = " + "".join(pieces)


def make_design_template(design_name: str, factor_count: int, center_points: int = 5) -> pd.DataFrame:
    factors = [f"X{i + 1}" for i in range(factor_count)]
    rows: list[dict[str, float | None]] = []

    if design_name == "CCD":
        alpha = (2**factor_count) ** 0.25
        for point in np.array(np.meshgrid(*[[-1.0, 1.0]] * factor_count)).T.reshape(-1, factor_count):
            rows.append(dict(zip(factors, point)))
        for i in range(factor_count):
            for sign in [-1.0, 1.0]:
                point = np.zeros(factor_count)
                point[i] = sign * alpha
                rows.append(dict(zip(factors, point)))
    elif design_name == "CCI":
        alpha = (2**factor_count) ** 0.25
        factorial_level = 1.0 / alpha
        for point in np.array(np.meshgrid(*[[-factorial_level, factorial_level]] * factor_count)).T.reshape(-1, factor_count):
            rows.append(dict(zip(factors, point)))
        for i in range(factor_count):
            for sign in [-1.0, 1.0]:
                point = np.zeros(factor_count)
                point[i] = sign
                rows.append(dict(zip(factors, point)))
    elif design_name == "CCF":
        for point in np.array(np.meshgrid(*[[-1.0, 1.0]] * factor_count)).T.reshape(-1, factor_count):
            rows.append(dict(zip(factors, point)))
        for i in range(factor_count):
            for sign in [-1.0, 1.0]:
                point = np.zeros(factor_count)
                point[i] = sign
                rows.append(dict(zip(factors, point)))
    elif design_name == "Box-Behnken":
        if factor_count < 3:
            raise ValueError("Box-Behnken 설계는 3요인 이상에서 사용합니다.")
        for i in range(factor_count):
            for j in range(i + 1, factor_count):
                for a in [-1.0, 1.0]:
                    for b in [-1.0, 1.0]:
                        point = np.zeros(factor_count)
                        point[i] = a
                        point[j] = b
                        rows.append(dict(zip(factors, point)))
    elif design_name == "Full factorial":
        for point in np.array(np.meshgrid(*[[-1.0, 1.0]] * factor_count)).T.reshape(-1, factor_count):
            rows.append(dict(zip(factors, point)))
    else:
        raise ValueError(f"지원하지 않는 설계입니다: {design_name}")

    for _ in range(center_points):
        rows.append({factor: 0.0 for factor in factors})

    template = pd.DataFrame(rows)
    for response in RESPONSE_COLUMNS:
        template[response] = np.nan
    return template


def coded_levels(data: pd.DataFrame, factors: list[str]) -> np.ndarray | None:
    coded_columns = []
    for factor in factors:
        values = data[factor].to_numpy(dtype=float)
        center = (np.nanmax(values) + np.nanmin(values)) / 2.0
        half_range = (np.nanmax(values) - np.nanmin(values)) / 2.0
        if half_range <= 0:
            return None
        coded_columns.append((values - center) / half_range)
    return np.column_stack(coded_columns)


def detect_design_type(data: pd.DataFrame, factors: list[str]) -> tuple[str, str]:
    coded = coded_levels(data, factors)
    if coded is None:
        return "판별 불가", "요인 범위가 0인 컬럼이 있어 설계유형을 추정할 수 없습니다."

    k = len(factors)
    tol_zero = 0.08
    abs_coded = np.abs(coded)
    nonzero_count = np.sum(abs_coded > tol_zero, axis=1)

    center_points = int(np.sum(nonzero_count == 0))
    axial_points = int(np.sum(nonzero_count == 1))
    full_corner_points = int(np.sum(nonzero_count == k))
    pair_edge_points = int(np.sum(nonzero_count == 2))

    has_center = center_points > 0
    has_axial = axial_points >= 2 * k
    has_full_corners = full_corner_points >= 2**k
    has_pair_edges = k >= 3 and pair_edge_points >= 4 * (k * (k - 1) // 2)

    if k >= 3 and has_pair_edges and not has_full_corners:
        return (
            "Box-Behnken 추정",
            f"2요인 조합의 모서리점과 중심점이 보이고, 전체 꼭짓점은 보이지 않습니다. 중심점 {center_points}개.",
        )

    if has_axial and has_full_corners and has_center:
        unique_abs_levels = sorted(
            {
                round(float(value), 3)
                for value in abs_coded.ravel()
                if value > tol_zero
            }
        )
        if len(unique_abs_levels) <= 1:
            return (
                "CCF 추정",
                f"모든 축점과 factorial 꼭짓점이 같은 ±1 수준에 있습니다. 중심점 {center_points}개.",
            )
        raw_values = data[factors].to_numpy(dtype=float)
        raw_centers = (
            np.nanmax(raw_values, axis=0) + np.nanmin(raw_values, axis=0)
        ) / 2.0
        raw_levels = np.abs(raw_values - raw_centers).ravel()
        raw_levels = raw_levels[raw_levels > 1e-10]
        alpha = (2**k) ** 0.25
        has_unit_level = bool(np.any(np.isclose(raw_levels, 1.0, rtol=0.03, atol=0.03)))
        has_ccd_axis = bool(np.any(np.isclose(raw_levels, alpha, rtol=0.03, atol=0.03)))
        has_cci_corner = bool(np.any(np.isclose(raw_levels, 1.0 / alpha, rtol=0.03, atol=0.03)))
        if has_unit_level and has_cci_corner and not has_ccd_axis:
            return (
                "CCI 추정",
                f"factorial 수준 ±{1.0 / alpha:.4g}와 축점 ±1이 보입니다. 중심점 {center_points}개.",
            )
        if has_unit_level and has_ccd_axis:
            return (
                "CCD 추정",
                f"factorial 수준 ±1과 회전성 축점 ±{alpha:.4g}가 보입니다. 중심점 {center_points}개.",
            )
        return (
            "중심합성(CCD/CCI) 추정",
            f"축점과 factorial 꼭짓점이 함께 있고 중심 거리 수준이 둘 이상입니다. 입력 범위 정보가 없어 CCD와 CCI는 구분하지 않았습니다. 중심점 {center_points}개.",
        )

    if has_full_corners and has_center and not has_axial:
        return (
            "Full factorial + center 추정",
            "꼭짓점과 중심점은 있으나 축점이 부족해 full quadratic RSM 설계로는 제한적일 수 있습니다.",
        )

    return (
        "사용자 정의/판별 불가",
        "점 배치가 표준 CCD, CCF, Box-Behnken 패턴과 명확히 일치하지 않습니다. 그래도 행 수와 rank가 충분하면 RSM 적합은 가능합니다.",
    )


def clean_numeric_data(df: pd.DataFrame, selected_columns: list[str]) -> tuple[pd.DataFrame, int]:
    numeric = df[selected_columns].copy()
    for col in selected_columns:
        numeric[col] = pd.to_numeric(numeric[col], errors="coerce")
    before = len(numeric)
    numeric = numeric.dropna()
    return numeric, before - len(numeric)


def default_index(options: list[str], value: str | None) -> int:
    if value in options:
        return options.index(value)
    return 0
