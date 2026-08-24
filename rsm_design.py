from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from rsm_core import *
from rsm_statistics import *


def make_actual_design_table(
    design_name: str,
    factor_count: int,
    ranges: dict[str, tuple[float, float]],
    center_points: int,
    random_seed: int | None = 42,
    batch_count: int = 1,
    max_runs_per_batch: int | None = None,
) -> pd.DataFrame:
    coded = make_design_template(design_name, factor_count, center_points=center_points)
    factors = [f"X{i + 1}" for i in range(factor_count)]
    coded = coded.copy()
    coded["StdOrder"] = np.arange(1, len(coded) + 1)
    center_mask = (coded[factors].abs().sum(axis=1) == 0)
    coded["PointType"] = np.where(center_mask, "Center", "Design")

    rng = np.random.default_rng(random_seed)
    design_rows = coded.loc[~center_mask].sample(frac=1, random_state=int(rng.integers(0, 2**31 - 1)))
    center_rows = coded.loc[center_mask].sample(frac=1, random_state=int(rng.integers(0, 2**31 - 1)))

    batch_count = max(1, int(batch_count))
    if len(center_rows) > 0 and batch_count > 1:
        design_chunks: list[pd.DataFrame] = [pd.DataFrame(columns=design_rows.columns) for _ in range(batch_count)]
        center_chunks: list[pd.DataFrame] = [pd.DataFrame(columns=center_rows.columns) for _ in range(batch_count)]

        capacities = [None if max_runs_per_batch is None else int(max_runs_per_batch) for _ in range(batch_count)]
        center_positions = [[] for _ in range(batch_count)]
        for idx in range(len(center_rows)):
            batch_idx = idx % batch_count
            center_positions[batch_idx].append(idx)
            if capacities[batch_idx] is not None:
                capacities[batch_idx] -= 1

        for batch_idx, positions in enumerate(center_positions):
            if positions:
                center_chunks[batch_idx] = center_rows.iloc[positions]

        design_positions = [[] for _ in range(batch_count)]
        for idx in range(len(design_rows)):
            if max_runs_per_batch is None:
                batch_idx = idx % batch_count
            else:
                available_batches = [
                    batch_idx
                    for batch_idx, remaining_capacity in enumerate(capacities)
                    if remaining_capacity is not None and remaining_capacity > 0
                ]
                if not available_batches:
                    batch_idx = idx % batch_count
                else:
                    batch_idx = max(available_batches, key=lambda candidate: capacities[candidate])
                    capacities[batch_idx] -= 1
            design_positions[batch_idx].append(idx)

        for batch_idx, positions in enumerate(design_positions):
            if positions:
                design_chunks[batch_idx] = design_rows.iloc[positions]

        ordered_parts = []
        for batch_idx, (design_chunk, center_chunk) in enumerate(zip(design_chunks, center_chunks), start=1):
            batch_rows = pd.concat([design_chunk, center_chunk], ignore_index=False)
            batch_rows = batch_rows.sample(frac=1, random_state=int(rng.integers(0, 2**31 - 1))).copy()
            batch_rows["Batch"] = batch_idx
            batch_rows["RunInBatch"] = np.arange(1, len(batch_rows) + 1)
            ordered_parts.append(batch_rows)
        coded = pd.concat(ordered_parts, ignore_index=True)
    elif len(center_rows) > 0:
        chunk_indices = np.array_split(np.arange(len(design_rows)), len(center_rows) + 1)
        chunks = [design_rows.iloc[indices] for indices in chunk_indices]
        ordered_parts = []
        for idx, chunk in enumerate(chunks):
            if len(chunk) > 0:
                ordered_parts.append(chunk)
            if idx < len(center_rows):
                ordered_parts.append(center_rows.iloc[[idx]])
        coded = pd.concat(ordered_parts, ignore_index=True)
        coded["Batch"] = 1
        coded["RunInBatch"] = np.arange(1, len(coded) + 1)
    else:
        coded = design_rows.reset_index(drop=True)
        coded["Batch"] = 1
        coded["RunInBatch"] = np.arange(1, len(coded) + 1)

    output = pd.DataFrame(
        {
            "Run": np.arange(1, len(coded) + 1),
            "Batch": coded["Batch"].astype(int),
            "RunInBatch": coded["RunInBatch"].astype(int),
            "StdOrder": coded["StdOrder"],
            "PointType": coded["PointType"],
        }
    )

    for factor in factors:
        low, high = ranges[factor]
        center = (low + high) / 2.0
        half_range = (high - low) / 2.0
        output[factor] = center + coded[factor].to_numpy(dtype=float) * half_range
        output[f"{factor}_coded"] = coded[factor].to_numpy(dtype=float)

    for response in RESPONSE_COLUMNS:
        output[response] = np.nan
    ordered_columns = (
        ["Run", "Batch", "PointType"]
        + factors
        + RESPONSE_COLUMNS
        + [f"{factor}_coded" for factor in factors]
        + ["RunInBatch", "StdOrder"]
    )
    return output[ordered_columns]


def design_result_columns(factors: list[str], responses: list[str]) -> list[str]:
    factor_columns = [
        column
        for factor in factors
        for column in (factor, f"{factor}_coded")
    ]
    return ["Run", "Batch", "PointType", *factor_columns, *responses]


def design_result_labels(
    factors: list[str],
    responses: list[str],
    response_labels: dict[str, str] | None = None,
    factor_codes: dict[str, str] | None = None,
    *,
    multiline: bool = False,
) -> dict[str, str]:
    labels = {
        "StdOrder": "설계순번",
        "Run": "실행순번",
        "Batch": "배치번호",
        "PointType": "포인트타입",
    }
    for factor in factors:
        factor_code = (factor_codes or {}).get(factor, factor)
        if factor_code == factor:
            labels[factor] = factor
            labels[f"{factor}_coded"] = f"{factor}coded"
        elif multiline:
            labels[factor] = f"{factor_code}\n{factor}"
            labels[f"{factor}_coded"] = f"{factor_code}coded\n{factor}coded"
        else:
            labels[factor] = f"{factor_code} ({factor})"
            labels[f"{factor}_coded"] = f"{factor_code}coded ({factor}coded)"
    for response in responses:
        display_name = (response_labels or {}).get(response, response)
        if display_name == response:
            labels[response] = response
        elif multiline:
            labels[response] = f"{response}\n{display_name}"
        else:
            labels[response] = f"{response} ({display_name})"
    return labels


def make_design_csv(
    design_df: pd.DataFrame,
    factors: list[str],
    responses: list[str],
    response_labels: dict[str, str] | None = None,
    factor_codes: dict[str, str] | None = None,
    *,
    blank_responses: bool,
) -> bytes:
    columns = design_result_columns(factors, responses)
    output_df = (
        design_df.sort_values("Run", kind="stable")
        .reset_index(drop=True)
        .loc[:, columns]
        .copy(deep=True)
    )
    if blank_responses:
        for response in responses:
            output_df[response] = np.nan
    output_df = output_df.rename(
        columns=design_result_labels(
            factors,
            responses,
            response_labels,
            factor_codes,
        )
    )
    return output_df.to_csv(index=False).encode("utf-8-sig")


def normalize_design_csv_columns(
    uploaded_df: pd.DataFrame,
    factors: list[str],
    responses: list[str],
    response_labels: dict[str, str] | None = None,
    factor_codes: dict[str, str] | None = None,
) -> pd.DataFrame:
    display_labels = design_result_labels(
        factors,
        responses,
        response_labels,
        factor_codes,
    )
    reverse_labels = {display_name: column for column, display_name in display_labels.items()}
    for factor in factors:
        factor_code = (factor_codes or {}).get(factor, factor)
        factor_column = factor
        coded_column = f"{factor}_coded"
        reverse_labels.update(
            {
                factor: factor_column,
                factor_code: factor_column,
                f"{factor_code} ({factor})": factor_column,
                f"{factor_code}\n{factor}": factor_column,
                coded_column: coded_column,
                f"{factor}coded": coded_column,
                f"{factor_code}_coded": coded_column,
                f"{factor_code}coded": coded_column,
                f"{factor_code}coded ({factor}coded)": coded_column,
                f"{factor_code}coded\n{factor}coded": coded_column,
            }
        )
    for response in responses:
        display_name = (response_labels or {}).get(response, response)
        reverse_labels[response] = response
        reverse_labels[display_name] = response
        reverse_labels[f"{response} ({display_name})"] = response
        reverse_labels[f"{display_name} ({response})"] = response
        reverse_labels[f"{response}\n{display_name}"] = response

    stripped_columns = {column: str(column).strip() for column in uploaded_df.columns}
    unsupported_responses: list[str] = []
    for stripped_name in stripped_columns.values():
        response_match = re.match(r"^Y(\d+)(?:\s*$|\s*[\(\n])", stripped_name, flags=re.IGNORECASE)
        if response_match and int(response_match.group(1)) > len(RESPONSE_COLUMNS):
            unsupported_responses.append(f"Y{int(response_match.group(1))}")
    if unsupported_responses:
        unsupported_label = ", ".join(sorted(set(unsupported_responses)))
        raise ValueError(
            f"{unsupported_label}은 지원하지 않습니다. "
            f"이 앱은 Y1~Y{len(RESPONSE_COLUMNS)}까지만 지원합니다."
        )

    normalized = uploaded_df.rename(columns=stripped_columns).rename(columns=reverse_labels)
    missing_responses = [response for response in responses if response not in normalized.columns]
    expected_columns = set(design_result_columns(factors, responses))
    structure_columns = set(design_result_columns(factors, []))
    missing_structure = [column for column in structure_columns if column not in normalized.columns]
    unmatched_columns = [
        column
        for column in normalized.columns
        if column not in expected_columns and column not in {"RunInBatch", "StdOrder"}
    ]
    if unmatched_columns and not missing_structure:
        if len(unmatched_columns) > len(missing_responses):
            raise ValueError(
                "반응값 열을 자동 대응할 수 없습니다: " + ", ".join(map(str, unmatched_columns))
            )
        normalized = normalized.rename(
            columns=dict(zip(unmatched_columns, missing_responses))
        )
    if normalized.columns.duplicated().any():
        duplicated = normalized.columns[normalized.columns.duplicated()].tolist()
        raise ValueError(f"중복 열: {', '.join(duplicated)}")
    return normalized


def infer_external_analysis_columns(data: pd.DataFrame) -> dict[str, list[str]]:
    if data.empty:
        raise ValueError("업로드한 CSV에 데이터가 없습니다.")

    stripped_names = [str(column).strip() for column in data.columns]
    if len(stripped_names) != len(set(stripped_names)):
        raise ValueError("CSV에 이름이 같은 열이 중복되어 있습니다.")

    unsupported_responses: list[str] = []
    unsupported_factors: list[str] = []
    explicit_factors: list[str] = []
    explicit_responses: list[str] = []
    numeric_columns: list[str] = []
    metadata_names = {
        "run",
        "batch",
        "runinbatch",
        "stdorder",
        "pointtype",
        "설계순번",
        "실행순번",
        "배치번호",
        "포인트타입",
    }

    for column, stripped_name in zip(data.columns, stripped_names):
        normalized_name = normalize_name(stripped_name)
        if normalized_name.startswith("unnamed:"):
            continue
        numeric = pd.to_numeric(data[column], errors="coerce")
        if numeric.notna().any():
            numeric_columns.append(column)

        response_match = re.match(
            r"^Y(\d+)(?:\s*$|\s*[\(\n])",
            stripped_name,
            flags=re.IGNORECASE,
        )
        if response_match:
            response_number = int(response_match.group(1))
            if response_number > len(RESPONSE_COLUMNS):
                unsupported_responses.append(f"Y{response_number}")
            elif column in numeric_columns:
                explicit_responses.append(column)

        is_coded = normalized_name.endswith("coded")
        factor_match = None if is_coded else re.match(
            r"^X(\d+)(?:\s*$|\s*[\(\n])",
            stripped_name,
            flags=re.IGNORECASE,
        )
        if factor_match:
            factor_number = int(factor_match.group(1))
            if factor_number > 3:
                unsupported_factors.append(f"X{factor_number}")
            elif column in numeric_columns:
                explicit_factors.append(column)

    if unsupported_responses:
        unsupported_label = ", ".join(sorted(set(unsupported_responses)))
        raise ValueError(
            f"{unsupported_label}은 지원하지 않습니다. "
            f"이 앱은 Y1~Y{len(RESPONSE_COLUMNS)}까지만 지원합니다."
        )
    if unsupported_factors:
        unsupported_label = ", ".join(sorted(set(unsupported_factors)))
        raise ValueError(
            f"{unsupported_label}은 지원하지 않습니다. 이 앱은 최대 3요인까지 지원합니다."
        )

    factor_columns = list(dict.fromkeys(explicit_factors))
    if len(factor_columns) < 2:
        factor_columns = []
        max_level_count = max(5, int(math.sqrt(max(len(data), 1))) + 1)
        for column in numeric_columns:
            normalized_name = normalize_name(column)
            if normalized_name in metadata_names or normalized_name.endswith("coded"):
                continue
            if column in explicit_responses:
                break
            unique_count = int(pd.to_numeric(data[column], errors="coerce").nunique(dropna=True))
            if unique_count < 2 or unique_count > max_level_count:
                if len(factor_columns) >= 2:
                    break
                continue
            factor_columns.append(column)
            if len(factor_columns) == 3:
                break

    if len(factor_columns) not in {2, 3}:
        raise ValueError(
            "X 요인 열을 자동 판별하지 못했습니다. X1, X2와 선택적인 X3 열을 포함해 주세요."
        )

    response_columns: list[str] = []
    for column in numeric_columns:
        normalized_name = normalize_name(column)
        if column in factor_columns:
            continue
        if normalized_name in metadata_names or normalized_name.endswith("coded"):
            continue
        response_columns.append(column)

    if not response_columns:
        raise ValueError("숫자 Y 결과 열을 찾지 못했습니다.")

    return {
        "factor_columns": factor_columns,
        "response_columns": list(dict.fromkeys(response_columns)),
        "numeric_columns": numeric_columns,
    }


def design_explanation(design_name: str, factor_count: int) -> str:
    term_count = len(build_terms(factor_count))
    explanations = {
        "CCD": (
            "CCD는 꼭짓점, 축점, 중심점을 함께 쓰는 대표적인 RSM 설계입니다. "
            "회전성에 유리하지만 축점이 입력한 최소/최대 범위 밖으로 나갈 수 있습니다."
        ),
        "CCI": (
            "CCI는 CCD를 입력 범위 안쪽에 넣은 형태입니다. 축점이 최소/최대에 놓이고, "
            "factorial 점은 그보다 안쪽에 배치되어 범위를 넘기지 않습니다."
        ),
        "CCF": (
            "CCF는 CCD의 face-centered 형태입니다. 축점이 각 요인의 최소/최대 면 중앙에 놓여 "
            "공정 범위를 넘기기 어려울 때 쓰기 좋습니다."
        ),
        "Box-Behnken": (
            "Box-Behnken은 전체 꼭짓점을 쓰지 않고 두 요인씩만 높은/낮은 수준으로 바꾸는 설계입니다. "
            "3요인 이상에서 쓸 수 있고 극단 조합을 피하고 싶을 때 유용합니다."
        ),
        "Full factorial": (
            "Full factorial은 모든 꼭짓점 조합과 중심점을 보는 기본 설계입니다. "
            "다만 full quadratic의 제곱항을 안정적으로 보려면 CCD/CCF/Box-Behnken이 보통 더 적합합니다."
        ),
    }
    return f"{explanations[design_name]} {factor_count}요인 full quadratic 모델은 계수 {term_count}개를 추정합니다."


def base_design_run_count(design_name: str, factor_count: int) -> int:
    if design_name == "Box-Behnken":
        return 4 * (factor_count * (factor_count - 1) // 2)
    if design_name in {"CCD", "CCI", "CCF"}:
        return 2**factor_count + 2 * factor_count
    if design_name == "Full factorial":
        return 2**factor_count
    raise ValueError(f"지원하지 않는 설계입니다: {design_name}")


def resolve_batch_plan(base_runs: int, requested_center_points: int, max_runs_per_batch: int) -> tuple[int, int, list[str]]:
    max_runs_per_batch = int(max_runs_per_batch)
    if max_runs_per_batch < 2:
        return max(1, requested_center_points), 1, ["Batch당 가능 Run 수는 최소 2 이상이어야 중심점과 설계점을 함께 배치할 수 있습니다."]

    requested_center_points = max(1, int(requested_center_points))
    warnings: list[str] = []

    batch_count = 1
    center_points = requested_center_points
    for candidate_batch_count in range(1, max(1000, base_runs + requested_center_points + 1)):
        candidate_center_points = max(requested_center_points, candidate_batch_count)
        total_capacity = candidate_batch_count * max_runs_per_batch
        total_runs = base_runs + candidate_center_points
        if total_runs <= total_capacity:
            batch_count = candidate_batch_count
            center_points = candidate_center_points
            break
    else:
        center_points = max(requested_center_points, base_runs)
        batch_count = center_points
        warnings.append("Batch/중심점 자동 계산이 안전한 범위를 찾지 못했습니다. Batch당 가능 Run 수를 늘려주세요.")

    if center_points != requested_center_points:
        warnings.append(
            f"각 Batch에 중심점을 넣기 위해 중심점을 {requested_center_points}개에서 {center_points}개로 자동 보정했습니다."
        )
    return center_points, batch_count, warnings


def valid_response_columns(data: pd.DataFrame, factors: list[str], candidates: list[str]) -> list[str]:
    responses = []
    for y_name in candidates:
        if y_name in data.columns:
            numeric, _ = clean_numeric_data(data, factors + [y_name])
            if len(numeric) > 0:
                responses.append(y_name)
    return responses

