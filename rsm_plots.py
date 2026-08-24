from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from rsm_core import *
from rsm_statistics import *


def add_stationary_trace_2d(fig: go.Figure, result: FitResult, stationary: StationaryPoint, axis_x: str, axis_y: str) -> None:
    if stationary.point is None:
        return
    point_map = dict(zip(result.factors, stationary.point))
    fig.add_trace(
        go.Scatter(
            x=[point_map[axis_x]],
            y=[point_map[axis_y]],
            mode="markers",
            marker=dict(size=12, color="red", symbol="x"),
            name="정상점",
        )
    )


def make_contour_figure(
    result: FitResult,
    data: pd.DataFrame,
    stationary: StationaryPoint,
    axis_x: str,
    axis_y: str,
    fixed_values: dict[str, float],
    grid_size: int,
) -> go.Figure:
    xx, yy, zz = predict_grid(result, axis_x, axis_y, fixed_values, grid_size)
    fig = go.Figure(
        data=go.Contour(
            x=xx[0, :],
            y=yy[:, 0],
            z=zz,
            name="예측 Contour",
            colorscale="Viridis",
            contours=dict(showlabels=True),
            colorbar=dict(
                title=dict(text=result.y_label, side="right", font=dict(size=15)),
                thickness=18,
                len=0.9,
                x=1.02,
            ),
            hovertemplate=f"{axis_x}=%{{x:.5g}}<br>{axis_y}=%{{y:.5g}}<br>{result.y_label}=%{{z:.5g}}<extra>예측 Contour</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=data[axis_x],
            y=data[axis_y],
            mode="markers",
            marker=dict(size=7, color="white", line=dict(color="#222", width=1)),
            name="실험점",
        )
    )
    add_stationary_trace_2d(fig, result, stationary, axis_x, axis_y)
    fig.update_layout(
        height=540,
        margin=dict(l=75, r=120, t=45, b=75),
        xaxis=dict(
            title=dict(text=axis_x, font=dict(size=16)),
            range=[float(result.x_min[axis_x]), float(result.x_max[axis_x])],
            automargin=True,
        ),
        yaxis=dict(
            title=dict(text=axis_y, font=dict(size=16)),
            range=[float(result.x_min[axis_y]), float(result.x_max[axis_y])],
            automargin=True,
        ),
    )
    return fig


def make_surface_figure(
    result: FitResult,
    data: pd.DataFrame,
    stationary: StationaryPoint,
    axis_x: str,
    axis_y: str,
    fixed_values: dict[str, float],
    grid_size: int,
) -> go.Figure:
    xx, yy, zz = predict_grid(result, axis_x, axis_y, fixed_values, grid_size)
    fig = go.Figure(
        data=go.Surface(
            x=xx,
            y=yy,
            z=zz,
            name="예측 Surface",
            colorscale="Viridis",
            colorbar=dict(
                title=dict(text=result.y_label, side="right", font=dict(size=15)),
                thickness=18,
                len=0.85,
                x=1.02,
            ),
            opacity=0.95,
            hovertemplate=f"{axis_x}=%{{x:.5g}}<br>{axis_y}=%{{y:.5g}}<br>{result.y_label}=%{{z:.5g}}<extra>예측 Surface</extra>",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=data[axis_x],
            y=data[axis_y],
            z=data[result.y_name],
            mode="markers",
            marker=dict(size=4, color="black"),
            name="실험점",
        )
    )
    if stationary.point is not None:
        point_map = dict(zip(result.factors, stationary.point))
        fig.add_trace(
            go.Scatter3d(
                x=[point_map[axis_x]],
                y=[point_map[axis_y]],
                z=[predict_single(result, stationary.point)],
                mode="markers",
                marker=dict(size=7, color="red", symbol="diamond"),
                name="정상점",
            )
        )
    fig.update_layout(
        height=540,
        margin=dict(l=35, r=120, t=45, b=45),
        scene=dict(
            xaxis=dict(title=dict(text=axis_x, font=dict(size=15))),
            yaxis=dict(title=dict(text=axis_y, font=dict(size=15))),
            zaxis=dict(title=dict(text=result.y_label, font=dict(size=15))),
        ),
    )
    return fig


def make_profile_figure(result: FitResult, hold_values: dict[str, float], grid_size: int = 80) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=len(result.factors),
        subplot_titles=result.factors,
        shared_yaxes=True,
    )
    for col_idx, factor in enumerate(result.factors, start=1):
        x_values = np.linspace(float(result.x_min[factor]), float(result.x_max[factor]), grid_size)
        rows = []
        for value in x_values:
            rows.append([value if current == factor else hold_values[current] for current in result.factors])
        y_values = design_matrix(np.asarray(rows, dtype=float), result.terms) @ result.beta
        fig.add_trace(
            go.Scatter(x=x_values, y=y_values, mode="lines", name=factor, showlegend=False),
            row=1,
            col=col_idx,
        )
        fig.add_vline(x=hold_values[factor], line_dash="dot", line_color="red", row=1, col=col_idx)
        fig.update_xaxes(title_text=factor, row=1, col=col_idx)
    fig.update_yaxes(title_text=result.y_label, row=1, col=1)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=45, b=10))
    return fig


def profile_trace_data(
    result: FitResult,
    hold_values: dict[str, float],
    factor: str,
    grid_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    x_values = np.linspace(float(result.x_min[factor]), float(result.x_max[factor]), grid_size)
    rows = []
    for value in x_values:
        rows.append([value if current == factor else hold_values[current] for current in result.factors])
    y_values = design_matrix(np.asarray(rows, dtype=float), result.terms) @ result.beta
    return x_values, y_values


def make_live_profile_figure(
    result: FitResult,
    base_hold_values: dict[str, float],
    slider_factor: str | None = None,
    steps_count: int = 31,
    grid_size: int = 100,
) -> go.Figure:
    subplot_titles = [
        f"{factor} profile" + (f" ({slider_factor} slider)" if slider_factor and factor != slider_factor else "")
        for factor in result.factors
    ]
    fig = make_subplots(
        rows=1,
        cols=len(result.factors),
        subplot_titles=subplot_titles,
        shared_yaxes=True,
    )

    if slider_factor is None:
        slider_values = np.asarray([base_hold_values[result.factors[0]]], dtype=float)
    else:
        slider_values = np.linspace(float(result.x_min[slider_factor]), float(result.x_max[slider_factor]), steps_count)

    all_frames = []
    global_y_min = np.inf
    global_y_max = -np.inf
    for slider_value in slider_values:
        hold_values = dict(base_hold_values)
        if slider_factor is not None:
            hold_values[slider_factor] = float(slider_value)

        frame_traces = []
        for factor in result.factors:
            x_values, y_values = profile_trace_data(result, hold_values, factor, grid_size)
            global_y_min = min(global_y_min, float(np.min(y_values)))
            global_y_max = max(global_y_max, float(np.max(y_values)))
            frame_traces.append(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    line=dict(width=3),
                    showlegend=False,
                )
            )
            frame_traces.append(
                go.Scatter(
                    x=[hold_values[factor], hold_values[factor]],
                    y=[float(np.min(y_values)), float(np.max(y_values))],
                    mode="lines",
                    line=dict(color="red", dash="dot", width=2),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        all_frames.append((float(slider_value), frame_traces))

    initial_traces = all_frames[len(all_frames) // 2][1] if slider_factor is not None else all_frames[0][1]
    for col_idx, _factor in enumerate(result.factors, start=1):
        fig.add_trace(initial_traces[(col_idx - 1) * 2], row=1, col=col_idx)
        fig.add_trace(initial_traces[(col_idx - 1) * 2 + 1], row=1, col=col_idx)

    frames = []
    for slider_value, frame_traces in all_frames:
        frames.append(go.Frame(name=format_number(slider_value, 6), data=frame_traces))
    fig.frames = frames

    if slider_factor is not None:
        midpoint_index = len(all_frames) // 2
        steps = []
        for slider_value, _frame_traces in all_frames:
            label = format_number(slider_value, 5)
            steps.append(
                {
                    "label": label,
                    "method": "animate",
                    "args": [
                        [label],
                        {
                            "mode": "immediate",
                            "frame": {"duration": 0, "redraw": True},
                            "transition": {"duration": 0},
                        },
                    ],
                }
            )
        fig.update_layout(
            sliders=[
                {
                    "active": midpoint_index,
                    "currentvalue": {"prefix": f"{slider_factor} = "},
                    "steps": steps,
                    "pad": {"t": 45},
                }
            ]
        )

    if np.isfinite(global_y_min) and np.isfinite(global_y_max):
        padding = (global_y_max - global_y_min) * 0.08 or 1.0
        fig.update_yaxes(range=[global_y_min - padding, global_y_max + padding])

    for col_idx, factor in enumerate(result.factors, start=1):
        fig.update_xaxes(title_text=factor, row=1, col=col_idx)
    fig.update_yaxes(title_text=result.y_label, row=1, col=1)
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=50, b=35),
        updatemenus=[],
    )
    return fig


def prediction_with_ci(
    result: FitResult,
    data: pd.DataFrame,
    x_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_train = data[result.factors].to_numpy(dtype=float)
    y = data[result.y_name].to_numpy(dtype=float)
    train_matrix = design_matrix(x_train, result.terms)
    pred_matrix = design_matrix(x_values, result.terms)
    y_pred = pred_matrix @ result.beta

    df_error = max(len(y) - result.rank, 1)
    mse = float(np.sum(result.residuals**2) / df_error)
    xtx_inv = np.linalg.pinv(train_matrix.T @ train_matrix)
    leverage = np.sum((pred_matrix @ xtx_inv) * pred_matrix, axis=1)
    se_mean = np.sqrt(np.maximum(0.0, mse * leverage))
    z_value = 1.96
    return y_pred, y_pred - z_value * se_mean, y_pred + z_value * se_mean


def desirability_values(y_values: np.ndarray, low: float, target: float, high: float) -> np.ndarray:
    if not (low < target < high):
        return np.full_like(y_values, np.nan, dtype=float)
    left = (y_values - low) / (target - low)
    right = (high - y_values) / (high - target)
    return np.clip(np.minimum(left, right), 0.0, 1.0)


def make_prediction_profiler_figure(
    result: FitResult,
    data: pd.DataFrame,
    current_values: dict[str, float],
    low: float,
    target: float,
    high: float,
    live_factor: str | None = None,
    live_steps: int = 41,
    grid_size: int = 100,
) -> go.Figure:
    col_count = len(result.factors) + 1
    fig = make_subplots(
        rows=2,
        cols=col_count,
        shared_yaxes=False,
        subplot_titles=result.factors + ["Desirability"] + [""] * col_count,
        horizontal_spacing=0.025,
        vertical_spacing=0.08,
    )

    y_axis_min = min(low, float(np.min(data[result.y_name])), target)
    y_axis_max = max(high, float(np.max(data[result.y_name])), target)
    y_padding = (y_axis_max - y_axis_min) * 0.1 or 1.0

    def build_traces(values: dict[str, float]) -> tuple[list[go.BaseTraceType], float, float]:
        current_x = np.asarray([[values[factor] for factor in result.factors]], dtype=float)
        current_y = float(predict_single(result, current_x.ravel()))
        current_d = float(desirability_values(np.asarray([current_y]), low, target, high)[0])
        traces: list[go.BaseTraceType] = []
        for factor in result.factors:
            x_grid = np.linspace(float(result.x_min[factor]), float(result.x_max[factor]), grid_size)
            rows = []
            for value in x_grid:
                rows.append([value if current == factor else values[current] for current in result.factors])
            x_matrix = np.asarray(rows, dtype=float)
            y_pred, y_low, y_high = prediction_with_ci(result, data, x_matrix)
            desirability = desirability_values(y_pred, low, target, high)
            traces.extend(
                [
                    go.Scatter(
                        x=np.concatenate([x_grid, x_grid[::-1]]),
                        y=np.concatenate([y_high, y_low[::-1]]),
                        fill="toself",
                        fillcolor="rgba(120,160,255,0.22)",
                        line=dict(color="rgba(0,0,0,0)"),
                        hoverinfo="skip",
                        showlegend=False,
                        name="95% CI",
                    ),
                    go.Scatter(
                        x=x_grid,
                        y=y_pred,
                        mode="lines",
                        line=dict(color="#333333", width=2),
                        showlegend=False,
                        name=f"{factor} profile",
                    ),
                    go.Scatter(
                        x=[values[factor], values[factor]],
                        y=[y_axis_min - y_padding, y_axis_max + y_padding],
                        mode="lines",
                        line=dict(color="#ff3b5c", dash="dot", width=2),
                        hoverinfo="skip",
                        showlegend=False,
                        name=f"{factor} current",
                    ),
                    go.Scatter(
                        x=x_grid,
                        y=desirability,
                        mode="lines",
                        line=dict(color="#555555", width=2),
                        showlegend=False,
                        name=f"{factor} desirability",
                    ),
                    go.Scatter(
                        x=[values[factor], values[factor]],
                        y=[-0.05, 1.05],
                        mode="lines",
                        line=dict(color="#ff3b5c", dash="dot", width=2),
                        hoverinfo="skip",
                        showlegend=False,
                        name=f"{factor} desirability current",
                    ),
                ]
            )
        traces.extend(
            [
                go.Scatter(
                    x=[0, current_d, 1],
                    y=[current_y, target, current_y],
                    mode="lines+markers",
                    line=dict(color="#333333", width=2),
                    marker=dict(color="white", line=dict(color="#333333", width=1), size=8),
                    showlegend=False,
                    name="Overall desirability",
                ),
                go.Scatter(
                    x=[0, current_d, 1],
                    y=[0, current_d, 1],
                    mode="lines",
                    line=dict(color="#555555", width=2),
                    showlegend=False,
                    hovertemplate="Desirability=%{y:.4f}<extra></extra>",
                ),
            ]
        )
        return traces, current_y, current_d

    initial_traces, _current_y, _current_d = build_traces(current_values)
    trace_index = 0
    for col_idx, factor in enumerate(result.factors, start=1):
        fig.add_trace(initial_traces[trace_index], row=1, col=col_idx)
        trace_index += 1
        fig.add_trace(initial_traces[trace_index], row=1, col=col_idx)
        trace_index += 1
        fig.add_trace(initial_traces[trace_index], row=1, col=col_idx)
        trace_index += 1
        fig.add_trace(initial_traces[trace_index], row=2, col=col_idx)
        trace_index += 1
        fig.add_trace(initial_traces[trace_index], row=2, col=col_idx)
        trace_index += 1
        fig.add_hline(y=target, line_dash="dot", line_color="#ff3b5c", row=1, col=col_idx)
        fig.add_hline(y=1.0, line_dash="dot", line_color="#ff3b5c", row=2, col=col_idx)
        fig.update_xaxes(title_text=factor, row=2, col=col_idx)
        fig.update_yaxes(range=[y_axis_min - y_padding, y_axis_max + y_padding], row=1, col=col_idx)
        fig.update_yaxes(range=[-0.05, 1.05], row=2, col=col_idx)

    fig.add_trace(initial_traces[trace_index], row=1, col=col_count)
    trace_index += 1
    fig.add_trace(initial_traces[trace_index], row=2, col=col_count)

    if live_factor is not None and live_factor in result.factors:
        live_values = np.linspace(float(result.x_min[live_factor]), float(result.x_max[live_factor]), live_steps)
        frames = []
        steps = []
        for value in live_values:
            frame_values = dict(current_values)
            frame_values[live_factor] = float(value)
            frame_traces, _frame_y, _frame_d = build_traces(frame_values)
            label = format_number(float(value), 6)
            frames.append(go.Frame(name=label, data=frame_traces))
            steps.append(
                {
                    "label": label,
                    "method": "animate",
                    "args": [
                        [label],
                        {
                            "mode": "immediate",
                            "frame": {"duration": 0, "redraw": True},
                            "transition": {"duration": 0},
                        },
                    ],
                }
            )
        fig.frames = frames
        active_index = int(np.argmin(np.abs(live_values - current_values[live_factor])))
        fig.update_layout(
            sliders=[
                {
                    "active": active_index,
                    "currentvalue": {"prefix": f"Live {live_factor} = "},
                    "steps": steps,
                    "pad": {"t": 45},
                }
            ]
        )

    fig.update_xaxes(title_text="Desirability", range=[-0.02, 1.02], row=1, col=col_count)
    fig.update_xaxes(title_text="Desirability", range=[-0.02, 1.02], row=2, col=col_count)
    fig.update_yaxes(range=[y_axis_min - y_padding, y_axis_max + y_padding], row=1, col=col_count)
    fig.update_yaxes(range=[-0.05, 1.05], row=2, col=col_count)
    fig.update_yaxes(title_text=result.y_label, row=1, col=1)
    fig.update_yaxes(title_text="Desirability", row=2, col=1)
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=45, b=10), showlegend=False)
    return fig


def make_jmp_style_contour_figure(
    result: FitResult,
    data: pd.DataFrame,
    stationary: StationaryPoint,
    axis_x: str,
    axis_y: str,
    fixed_values: dict[str, float],
    current_values: dict[str, float],
    low: float,
    target: float,
    high: float,
    grid_size: int = 80,
) -> go.Figure:
    xx, yy, zz = predict_grid(result, axis_x, axis_y, fixed_values, grid_size)
    desirability_grid = desirability_values(zz, low, target, high)
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            x=xx[0, :],
            y=yy[:, 0],
            z=desirability_grid,
            zmin=0,
            zmax=1,
            colorscale=[
                [0.0, "rgba(255,185,195,0.75)"],
                [0.35, "rgba(255,220,225,0.65)"],
                [1.0, "rgba(255,255,255,0.95)"],
            ],
            showscale=False,
            hovertemplate=f"{axis_x}=%{{x:.5g}}<br>{axis_y}=%{{y:.5g}}<br>Desirability=%{{z:.4f}}<extra>허용영역</extra>",
            name="허용영역",
        )
    )
    fig.add_trace(
        go.Contour(
            x=xx[0, :],
            y=yy[:, 0],
            z=zz,
            contours=dict(start=target, end=target, size=1, coloring="none", showlabels=True),
            line=dict(color="#e23b55", width=3),
            name=f"{result.y_label}={format_number(target, 5)}",
            showscale=False,
            hovertemplate=f"{axis_x}=%{{x:.5g}}<br>{axis_y}=%{{y:.5g}}<br>{result.y_label}=%{{z:.5g}}<extra>목표 Contour</extra>",
        )
    )
    fig.add_trace(
        go.Contour(
            x=xx[0, :],
            y=yy[:, 0],
            z=zz,
            contours=dict(start=low, end=high, size=high - low, coloring="none", showlabels=True),
            line=dict(color="#e23b55", width=1, dash="dot"),
            name="Lo/Hi limit",
            showscale=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=data[axis_x],
            y=data[axis_y],
            mode="markers",
            marker=dict(size=6, color="white", line=dict(color="#222", width=1)),
            name="실험점",
        )
    )
    if stationary.point is not None:
        add_stationary_trace_2d(fig, result, stationary, axis_x, axis_y)
    fig.add_vline(x=current_values[axis_x], line_color="#222222", line_width=2)
    fig.add_hline(y=current_values[axis_y], line_color="#222222", line_width=2)
    fig.update_layout(
        height=620,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title=axis_x,
        yaxis_title=axis_y,
    )
    return fig


def make_prediction_diagnostic_figure(result: FitResult, data: pd.DataFrame) -> go.Figure:
    observed = data[result.y_name].to_numpy(dtype=float)
    predicted = result.y_hat
    residuals = result.residuals
    low = float(min(np.min(observed), np.min(predicted)))
    high = float(max(np.max(observed), np.max(predicted)))

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["실측값 vs 예측값", "예측값 vs 잔차"],
    )
    fig.add_trace(
        go.Scatter(
            x=observed,
            y=predicted,
            mode="markers",
            marker=dict(size=8, color="#2563eb", line=dict(color="white", width=1)),
            name="실험점",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[low, high],
            y=[low, high],
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="완전일치선",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=predicted,
            y=residuals,
            mode="markers",
            marker=dict(size=8, color="#16a34a", line=dict(color="white", width=1)),
            name="잔차",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="red", row=1, col=2)
    fig.update_xaxes(title_text="실측값", row=1, col=1)
    fig.update_yaxes(title_text="예측값", row=1, col=1)
    fig.update_xaxes(title_text="예측값", row=1, col=2)
    fig.update_yaxes(title_text="잔차", row=1, col=2)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=45, b=10))
    return fig



