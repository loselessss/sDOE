from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd

from rsm_core import *
from rsm_plots import *
from rsm_statistics import *


def make_rsm_result_excel_file(
    source_df: pd.DataFrame,
    model_df: pd.DataFrame,
    result: FitResult,
    stationary: StationaryPoint,
    design_label: str,
    design_note: str,
    plot_axes: list[str],
    fixed_values: dict[str, float],
    grid_size: int,
    profiler_axis_x: str,
    profiler_axis_y: str,
    profiler_fixed_values: dict[str, float],
    current_values: dict[str, float],
    low_limit: float,
    target_value: float,
    high_limit: float,
    anova: pd.DataFrame,
    lack_of_fit: pd.DataFrame | None,
) -> bytes:
    axis_x, axis_y = plot_axes
    xx, yy, zz = predict_grid(result, axis_x, axis_y, fixed_values, grid_size)
    contour_df = pd.DataFrame(
        {
            axis_x: xx.ravel(),
            axis_y: yy.ravel(),
            f"Predicted {result.y_label}": zz.ravel(),
            **{factor: value for factor, value in fixed_values.items()},
        }
    )

    pxx, pyy, pzz = predict_grid(result, profiler_axis_x, profiler_axis_y, profiler_fixed_values, grid_size)
    contour_profiler_df = pd.DataFrame(
        {
            profiler_axis_x: pxx.ravel(),
            profiler_axis_y: pyy.ravel(),
            f"Predicted {result.y_label}": pzz.ravel(),
            "Desirability": desirability_values(pzz.ravel(), low_limit, target_value, high_limit),
            **{factor: value for factor, value in profiler_fixed_values.items()},
        }
    )

    profile_rows = []
    for factor in result.factors:
        x_grid = np.linspace(float(result.x_min[factor]), float(result.x_max[factor]), grid_size)
        rows = []
        for value in x_grid:
            rows.append([value if current == factor else current_values[current] for current in result.factors])
        x_matrix = np.asarray(rows, dtype=float)
        y_pred, y_low, y_high = prediction_with_ci(result, model_df, x_matrix)
        d_values = desirability_values(y_pred, low_limit, target_value, high_limit)
        for x_value, y_value, lo_ci, hi_ci, d_value in zip(x_grid, y_pred, y_low, y_high, d_values):
            profile_rows.append(
                {
                    "Moved Factor": factor,
                    "Factor Value": x_value,
                    f"Predicted {result.y_label}": y_value,
                    "Lower 95% CI": lo_ci,
                    "Upper 95% CI": hi_ci,
                    "Desirability": d_value,
                    **{f"Current {name}": current_values[name] for name in result.factors},
                }
            )
    profile_df = pd.DataFrame(profile_rows)

    predicted_df = model_df.copy()
    predicted_df["Predicted"] = result.y_hat
    predicted_df["Residual"] = result.residuals

    stationary_df = pd.DataFrame(
        {
            "Factor": result.factors,
            "Stationary Point": stationary.point if stationary.point is not None else [np.nan] * len(result.factors),
            "Experimental Min": [result.x_min[factor] for factor in result.factors],
            "Experimental Max": [result.x_max[factor] for factor in result.factors],
        }
    )
    stationary_df["Inside Range"] = (
        (stationary_df["Stationary Point"] >= stationary_df["Experimental Min"])
        & (stationary_df["Stationary Point"] <= stationary_df["Experimental Max"])
    )

    summary_df = pd.DataFrame(
        [
            {"Item": "Response", "Value": result.y_label},
            {"Item": "Factors", "Value": ", ".join(result.factors)},
            {"Item": "Design estimate", "Value": design_label},
            {"Item": "Design note", "Value": design_note},
            {"Item": "Equation", "Value": equation_text(result)},
            {"Item": "R squared", "Value": result.r2},
            {"Item": "Adjusted R squared", "Value": result.adj_r2},
            {"Item": "Valid rows", "Value": len(model_df)},
            {"Item": "Stationary classification", "Value": stationary.classification},
            {"Item": "Stationary message", "Value": stationary.message},
            {"Item": "Contour axes", "Value": ", ".join(plot_axes)},
            {"Item": "Target", "Value": target_value},
            {"Item": "Lo Limit", "Value": low_limit},
            {"Item": "Hi Limit", "Value": high_limit},
        ]
    )

    hessian_df = pd.DataFrame({"Hessian Eigenvalue": stationary.eigenvalues})
    current_df = pd.DataFrame(
        [
            {
                **{factor: current_values[factor] for factor in result.factors},
                f"Predicted {result.y_label}": predict_single(
                    result, np.asarray([current_values[factor] for factor in result.factors], dtype=float)
                ),
            }
        ]
    )

    buffer = BytesIO()
    export_source_df = source_df.drop(
        columns=["StdOrder", "RunInBatch"],
        errors="ignore",
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        export_source_df.to_excel(writer, sheet_name="Input Data", index=False)
        contour_df.to_excel(writer, sheet_name="Contour", index=False)
        contour_df.to_excel(writer, sheet_name="3D Surface", index=False)
        profile_df.to_excel(writer, sheet_name="Prediction Profiler", index=False)
        contour_profiler_df.to_excel(writer, sheet_name="Contour Profiler", index=False)
        predicted_df.to_excel(writer, sheet_name="Predicted Plot", index=False)
        anova.to_excel(writer, sheet_name="ANOVA", index=False)
        if lack_of_fit is not None:
            lack_of_fit.to_excel(writer, sheet_name="Lack of Fit", index=False)
        coefficient_table(result).to_excel(writer, sheet_name="Model Coeffs", index=False)
        stationary_df.to_excel(writer, sheet_name="Stationary", index=False)
        hessian_df.to_excel(writer, sheet_name="Hessian", index=False)
        current_df.to_excel(writer, sheet_name="Current Setting", index=False)
        predicted_df.to_excel(writer, sheet_name="Residuals", index=False)
        apply_excel_number_format(writer)
    return buffer.getvalue()


