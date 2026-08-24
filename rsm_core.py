from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st

from rsm_config import RESPONSE_COLUMNS
from rsm_i18n import t


@dataclass
class FitResult:
    factors: list[str]
    terms: list[tuple[str, tuple[int, ...]]]
    beta: np.ndarray
    r2: float
    adj_r2: float
    y_hat: np.ndarray
    residuals: np.ndarray
    rank: int
    condition_number: float
    x_min: pd.Series
    x_max: pd.Series
    y_name: str
    y_label: str


@dataclass
class StationaryPoint:
    is_unique: bool
    point: np.ndarray | None
    eigenvalues: np.ndarray
    classification: str
    message: str


def normalize_name(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "")


def guess_column(columns: Iterable[str], target: str) -> str | None:
    normalized = {normalize_name(col): col for col in columns}
    aliases = {
        "X1": ["x1", "factor1", "a", "변수1", "요인1"],
        "X2": ["x2", "factor2", "b", "변수2", "요인2"],
        "X3": ["x3", "factor3", "c", "변수3", "요인3"],
        "Y1": ["y1", "response1", "resp1", "결과1", "반응1"],
        "Y2": ["y2", "response2", "resp2", "결과2", "반응2"],
        "Y3": ["y3", "response3", "resp3", "결과3", "반응3"],
        "Y4": ["y4", "response4", "resp4", "결과4", "반응4"],
        "Y5": ["y5", "response5", "resp5", "결과5", "반응5"],
        "Y6": ["y6", "response6", "resp6", "결과6", "반응6"],
    }
    for key in aliases[target]:
        if normalize_name(key) in normalized:
            return normalized[normalize_name(key)]
    return None


@st.cache_data(show_spinner=False)
def get_sheet_names(file_bytes: bytes) -> list[str]:
    workbook = pd.ExcelFile(BytesIO(file_bytes))
    return workbook.sheet_names


@st.cache_data(show_spinner=False)
def read_uploaded_table(
    file_bytes: bytes,
    file_name: str,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(BytesIO(file_bytes))
        except UnicodeDecodeError:
            return pd.read_csv(BytesIO(file_bytes), encoding="cp949")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)
    raise ValueError("CSV, XLSX, XLS 파일만 지원합니다.")


def parse_plain_response_values(text: str, max_rows: int, max_cols: int = 3) -> pd.DataFrame:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not cleaned or max_rows <= 0 or max_cols <= 0:
        return pd.DataFrame()

    rows: list[list[str]] = []
    for raw_line in cleaned.split("\n"):
        if not raw_line.strip():
            break
        if "\t" in raw_line:
            cells = raw_line.split("\t")
        elif "," in raw_line:
            cells = next(csv.reader([raw_line]))
        else:
            cells = raw_line.split()
        trimmed = [cell.strip() for cell in cells]
        if not trimmed or trimmed[0] == "":
            break
        rows.append(trimmed[:max_cols])
        if len(rows) >= max_rows:
            break

    if not rows:
        return pd.DataFrame()

    width = min(max_cols, max(len(row) for row in rows))
    padded = [row + [""] * (width - len(row)) for row in rows]
    numeric = pd.DataFrame(padded).apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return numeric.reset_index(drop=True)


def apply_plain_response_to_design(
    design_df: pd.DataFrame,
    response_values: pd.DataFrame,
    response_columns: list[str],
) -> pd.DataFrame:
    merged = design_df.copy()
    if response_values.empty:
        return merged

    for index, response in enumerate(response_columns[: response_values.shape[1]]):
        target_index = merged.index[: len(response_values)]
        merged.loc[target_index, response] = response_values.iloc[:, index].to_numpy()
    return merged


def response_frame_from_table_payload(
    payload: object,
    response_columns: list[str],
    row_count: int,
) -> pd.DataFrame:
    if not isinstance(payload, dict) or not isinstance(payload.get("values"), list):
        return pd.DataFrame(index=range(row_count), columns=response_columns, dtype=float)

    values = pd.DataFrame(payload["values"])
    values = values.reindex(index=range(row_count), columns=response_columns)
    return values.apply(pd.to_numeric, errors="coerce")


def resolve_response_input(
    design_input_df: pd.DataFrame,
    edited_candidate: pd.DataFrame,
    response_columns: list[str],
    plain_response_active: bool,
) -> tuple[pd.DataFrame, str]:
    resolved = design_input_df.copy()
    if plain_response_active:
        return resolved, "plain_text"

    for response in response_columns:
        resolved[response] = pd.to_numeric(edited_candidate[response], errors="coerce").to_numpy()
    return resolved, "data_editor"


def apply_excel_number_format(writer: pd.ExcelWriter, number_format: str = "0.0000") -> None:
    workbook = writer.book
    skip_headers = {"Run", "Batch", "RunInBatch", "StdOrder", "PointType"}
    for worksheet in workbook.worksheets:
        for column_cells in worksheet.iter_cols(min_row=1):
            header = column_cells[0].value
            if header in skip_headers:
                continue
            for cell in column_cells[1:]:
                if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    cell.number_format = number_format


def dataframe_signature(df: pd.DataFrame) -> str:
    normalized = df.copy()
    for response in RESPONSE_COLUMNS:
        if response in normalized.columns:
            normalized[response] = np.nan
    hashed = pd.util.hash_pandas_object(normalized.astype(str), index=True).to_numpy().tobytes()
    return hashlib.sha1(hashed).hexdigest()[:16]


def build_terms(k: int) -> list[tuple[str, tuple[int, ...]]]:
    terms: list[tuple[str, tuple[int, ...]]] = [("Intercept", ())]
    terms.extend((f"x{i + 1}", (i,)) for i in range(k))
    for i in range(k):
        for j in range(i + 1, k):
            terms.append((f"x{i + 1}:x{j + 1}", (i, j)))
    terms.extend((f"x{i + 1}^2", (i, i)) for i in range(k))
    return terms


def design_matrix(x: np.ndarray, terms: list[tuple[str, tuple[int, ...]]]) -> np.ndarray:
    columns: list[np.ndarray] = []
    for _, idxs in terms:
        if len(idxs) == 0:
            columns.append(np.ones(x.shape[0]))
        elif len(idxs) == 1:
            columns.append(x[:, idxs[0]])
        else:
            columns.append(x[:, idxs[0]] * x[:, idxs[1]])
    return np.column_stack(columns)


def fit_quadratic_model(
    data: pd.DataFrame,
    factors: list[str],
    y_name: str,
    y_label: str | None = None,
) -> FitResult:
    x = data[factors].to_numpy(dtype=float)
    y = data[y_name].to_numpy(dtype=float)
    terms = build_terms(len(factors))
    matrix = design_matrix(x, terms)

    beta, _, rank, _ = np.linalg.lstsq(matrix, y, rcond=None)
    y_hat = matrix @ beta
    residuals = y - y_hat
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan

    n = len(y)
    p = matrix.shape[1]
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - p) if n > p and np.isfinite(r2) else np.nan

    singular_values = np.linalg.svd(matrix, compute_uv=False)
    if np.min(singular_values) > 0:
        condition_number = float(np.max(singular_values) / np.min(singular_values))
    else:
        condition_number = np.inf

    return FitResult(
        factors=factors,
        terms=terms,
        beta=beta,
        r2=r2,
        adj_r2=adj_r2,
        y_hat=y_hat,
        residuals=residuals,
        rank=rank,
        condition_number=condition_number,
        x_min=data[factors].min(),
        x_max=data[factors].max(),
        y_name=y_name,
        y_label=y_label or y_name,
    )


def coefficient_table(result: FitResult) -> pd.DataFrame:
    labels = []
    for term_name, idxs in result.terms:
        if term_name == "Intercept":
            labels.append("상수항")
        elif len(idxs) == 1:
            labels.append(result.factors[idxs[0]])
        elif idxs[0] == idxs[1]:
            labels.append(f"{result.factors[idxs[0]]}^2")
        else:
            labels.append(f"{result.factors[idxs[0]]} x {result.factors[idxs[1]]}")
    return pd.DataFrame({t("항"): labels, t("계수"): result.beta})


def gradient_components(result: FitResult) -> tuple[np.ndarray, np.ndarray]:
    k = len(result.factors)
    linear = np.zeros(k)
    hessian = np.zeros((k, k))

    for beta, (_, idxs) in zip(result.beta, result.terms):
        if len(idxs) == 1:
            linear[idxs[0]] += beta
        elif len(idxs) == 2 and idxs[0] == idxs[1]:
            hessian[idxs[0], idxs[0]] += 2.0 * beta
        elif len(idxs) == 2:
            i, j = idxs
            hessian[i, j] += beta
            hessian[j, i] += beta
    return linear, hessian


def compute_stationary_point(result: FitResult) -> StationaryPoint:
    linear, hessian = gradient_components(result)
    eigenvalues = np.linalg.eigvalsh(hessian)
    tol = max(1e-10, np.linalg.norm(hessian, ord=2) * 1e-9)
    rank = np.linalg.matrix_rank(hessian, tol=tol)

    if np.all(eigenvalues > tol):
        classification = "국소 최소점"
    elif np.all(eigenvalues < -tol):
        classification = "국소 최대점"
    elif np.any(eigenvalues > tol) and np.any(eigenvalues < -tol):
        classification = "안장점"
    else:
        classification = "평탄/퇴화 지점"

    if rank == len(result.factors):
        point = np.linalg.solve(hessian, -linear)
        return StationaryPoint(
            is_unique=True,
            point=point,
            eigenvalues=eigenvalues,
            classification=classification,
            message="gradient=0을 만족하는 고유한 정상점을 계산했습니다.",
        )

    try:
        point = np.linalg.pinv(hessian) @ (-linear)
        residual = np.linalg.norm(hessian @ point + linear)
        if residual < 1e-7:
            message = "Hessian이 특이행렬이라 정상점이 고유하지 않습니다. 아래 값은 최소 노름 해입니다."
            return StationaryPoint(False, point, eigenvalues, classification, message)
    except np.linalg.LinAlgError:
        pass

    return StationaryPoint(
        is_unique=False,
        point=None,
        eigenvalues=eigenvalues,
        classification=classification,
        message="Hessian이 특이행렬이고 gradient=0 해를 안정적으로 구할 수 없습니다.",
    )


def predict_grid(
    result: FitResult,
    axis_x: str,
    axis_y: str,
    fixed_values: dict[str, float],
    grid_size: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_range = np.linspace(float(result.x_min[axis_x]), float(result.x_max[axis_x]), grid_size)
    y_range = np.linspace(float(result.x_min[axis_y]), float(result.x_max[axis_y]), grid_size)
    xx, yy = np.meshgrid(x_range, y_range)

    rows = []
    for factor in result.factors:
        if factor == axis_x:
            rows.append(xx.ravel())
        elif factor == axis_y:
            rows.append(yy.ravel())
        else:
            rows.append(np.full(xx.size, fixed_values[factor]))
    grid_x = np.column_stack(rows)
    zz = design_matrix(grid_x, result.terms) @ result.beta
    return xx, yy, zz.reshape(xx.shape)

