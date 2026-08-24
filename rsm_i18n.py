from __future__ import annotations

from contextvars import ContextVar
import json
import os
from pathlib import Path
import re
from typing import Any, Callable


LANGUAGE_LABELS = {
    "ko": "한국어",
    "en": "International (English)",
}

_LANGUAGE: ContextVar[str] = ContextVar("rsm_language", default="ko")


ENGLISH = {
    "DOE 실험설계 + RSM 분석 앱": "DOE design + RSM analysis",
    "실험표를 만들거나 CSV/XLSX를 업로드한 뒤, Y 값을 입력하면 바로 RSM, contour, profiler를 확인합니다.": "Create a DOE worksheet or upload CSV/XLSX data, enter response values, and inspect the RSM, contours, and profilers immediately.",
    "다운로드 버튼을 누른 파일은 앱 폴더가 아니라 브라우저의 기본 다운로드 폴더에 저장됩니다. 보통 Windows의 '다운로드' 폴더이며, 브라우저 설정에 따라 위치가 달라질 수 있습니다.": "Downloaded files are saved through the browser. The desktop app asks where to save each file; browser behavior may vary by its download settings.",
    "입력 초기화": "Reset inputs",
    "업로드 파일, 붙여넣기 내용, 컬럼 매핑, 설계표 입력값을 비우고 처음 상태로 돌아갑니다.": "Clear uploaded files, pasted values, column mappings, and worksheet entries.",
    "기존 실험결과 CSV 업로드": "Upload existing experiment CSV",
    "앞에서 만든 설계와 실험 건수를 무시하고 CSV의 X·Y 열을 판별해 바로 분석합니다.": "Ignore the generated design and detect X and Y columns directly from an existing CSV.",
    "열 인식 확인": "Review detected columns",
    "X 요인 열": "X factor columns",
    "앱이 자동 판별한 2개 또는 3개의 요인 열입니다.": "The two or three factor columns detected by the app.",
    "Y 결과 열": "Y response columns",
    "X 요인 열은 2개 또는 3개를 선택해야 합니다.": "Select two or three X factor columns.",
    "Y 결과 열을 하나 이상 선택해야 합니다.": "Select at least one Y response column.",
    "반응값 이름": "Response names",
    "**반응값 이름**": "**Response names**",
    "반응값 수": "Number of responses",
    "분석할 Y 반응값 열의 개수입니다. Y1부터 Y6까지 사용할 수 있습니다.": "Number of response columns to analyze. Y1 through Y6 are supported.",
    "사용 중인 반응값 이름은 서로 달라야 합니다.": "Active response names must be unique.",
    "설계": "Design",
    "결과입력": "Results input",
    "분석": "Analysis",
    "외부 실험결과 CSV를 사용 중입니다. 앞에서 만든 실험설계는 이번 분석에 사용하지 않습니다.": "An external experiment CSV is active. The generated design is not used for this analysis.",
    "업로드한 파일에서 자동 인식한 X·Y 열입니다. 열 선택을 바꾸려면 위의 '열 인식 확인'을 여세요.": "These X and Y columns were detected from the uploaded file. Open 'Review detected columns' above to change them.",
    "RSM 결과": "RSM results",
    "유효한 X·Y 행으로 full quadratic RSM을 적합합니다. 반응값과 표시 축을 선택한 뒤 Contour, 3D Surface, Profiler, 예측 진단, ANOVA와 정상점을 확인하세요.": "Fit a full quadratic RSM with valid X and Y rows. Select a response and plot axes, then inspect contours, the 3D surface, profilers, prediction diagnostics, ANOVA, and the stationary point.",
    "업로드한 CSV에서 분석 가능한 숫자 Y값을 찾지 못했습니다.": "No numeric Y values suitable for analysis were found in the uploaded CSV.",
    "결과입력 탭에서 Y값을 입력하면 이 탭에 RSM 분석 결과가 표시됩니다.": "Enter Y values on the Results input tab to display the RSM analysis here.",
    "요인 수·이름·범위와 설계 종류를 정합니다. Batch당 Run 수, 중심점 반복 수와 seed를 반영해 실험 순서를 랜덤화합니다.": "Choose the factor count, names, ranges, and design. Runs are randomized using the batch capacity, center-point replicates, and seed.",
    "실험 설계 생성": "Generate DOE design",
    "요인 수": "Number of factors",
    "실험 설계 종류": "Design type",
    "Batch당 가능 Run 수": "Runs available per batch",
    "총 중심점 반복 수": "Total center-point replicates",
    "랜덤 실험순서 seed": "Random run-order seed",
    "**요인 이름과 최소/최대값**": "**Factor names and ranges**",
    "요인 이름이 중복되었습니다. 서로 다른 이름을 입력하세요.": "Factor names are duplicated. Enter unique names.",
    "요인 이름과 반응값 이름은 서로 달라야 합니다.": "Factor and response names must be different.",
    "CCD는 회전성 때문에 축점이 입력한 최소/최대 범위 밖으로 나갈 수 있습니다. 범위를 넘기면 위험한 공정은 CCF를 고려하세요.": "CCD axial points may fall outside the entered ranges to preserve rotatability. Consider CCF when exceeding a process range is unsafe.",
    "CCI는 입력한 최소/최대 범위를 넘기지 않도록 factorial 점을 안쪽으로 넣은 CCD 계열 설계입니다.": "CCI keeps all runs within the entered ranges by moving factorial points inward.",
    "CCF는 축점이 각 요인의 최소/최대 면 중앙에 놓이며, 모든 실험점이 입력한 범위 안에 배치되는 CCD 계열 설계입니다.": "CCF places axial points at the centers of the factor-range faces, keeping every run inside the entered ranges.",
    "Full factorial + 중심점만으로는 제곱항 추정이 불안정할 수 있습니다. RSM 최적화 목적이면 CCF, CCD, Box-Behnken을 권장합니다.": "A full factorial design with center points alone may estimate quadratic terms poorly. CCF, CCD, or Box-Behnken is recommended for RSM optimization.",
    "인쇄 참고사항": "Print notes",
    "시료 준비, 작업 조건, 주의사항 등을 입력하세요.": "Enter sample preparation, operating conditions, or precautions.",
    "입력한 내용은 인쇄물의 요인 범위 옆 참고사항 칸에 표시됩니다. 비워 두면 손으로 적을 공간으로 인쇄됩니다.": "These notes appear beside the factor ranges on the printout. Leave blank to create a handwritten notes area.",
    "실험계획 CSV 다운로드": "Download DOE plan CSV",
    "설계표는 실제 수행할 실행순번대로 표시합니다. 같은 Batch의 실험은 연속해서 나오며, Batch 안의 실험점 순서는 seed로 랜덤화됩니다.": "The worksheet is shown in execution order. Runs in the same batch stay together and are randomized within the batch using the seed.",
    "실험표 업로드": "Upload completed worksheet",
    "실험계획 CSV에 결과값을 입력한 파일을 업로드합니다.": "Upload a DOE plan CSV after entering the response values.",
    "실험표 CSV 파일": "DOE worksheet CSV",
    "입력한 실험표 CSV 다운로드": "Download completed worksheet CSV",
    "결과값을 붙여넣거나 직접 입력하세요.": "Paste or enter response values.",
    "현재 Streamlit 버전에서는 표 직접 붙여넣기 구성요소를 사용할 수 없습니다.": "The direct-paste table component is unavailable in this Streamlit version.",
    "사용 중인 Y열에 값을 입력하면 바로 RSM 분석이 표시됩니다.": "Enter values in an active Y column to display the RSM analysis.",
    "반응값": "Response",
    "그래프와 통계표에서 분석할 Y 반응값을 선택합니다.": "Select the Y response to use in plots and statistical tables.",
    "Contour 축": "Contour axes",
    "그림 해상도": "Plot resolution",
    "Contour와 3D Surface를 계산할 격자 수입니다. 높을수록 부드럽지만 계산량이 늘어납니다.": "Grid size used for contours and the 3D surface. Higher values are smoother but require more computation.",
    "Contour 축을 정확히 2개 선택하세요.": "Select exactly two contour axes.",
    "설계행렬의 rank가 부족합니다. 일부 계수가 독립적으로 추정되지 않을 수 있습니다.": "The design matrix is rank deficient. Some coefficients may not be independently estimable.",
    "설계행렬의 조건수가 매우 큽니다. 계수와 정상점이 작은 데이터 변화에 민감할 수 있습니다.": "The design matrix has a very large condition number. Coefficients and the stationary point may be sensitive to small data changes.",
    "그래프 축으로 선택하지 않은 요인을 이 값으로 고정합니다.": "Hold factors not selected as plot axes at this value.",
    "유효 행": "Valid rows",
    "설계 추정": "Estimated design",
    "모델/정상점": "Model / stationary point",
    "두 요인의 조합에 따른 예측 반응값을 등고선으로 표시합니다. 3요인 설계에서는 선택하지 않은 요인을 위에서 지정한 값으로 고정합니다.": "Display predicted responses for two factors as contours. For a three-factor design, the unselected factor is held at the value set above.",
    "Contour 그래프 HTML 저장": "Save contour as HTML",
    "Contour와 같은 예측면을 회전 가능한 3D로 확인합니다. 곡률과 최대점·최소점·안장점의 형태를 살펴보고 HTML·GLB로 저장할 수 있습니다.": "Inspect the predicted surface as an interactive 3D plot. Review curvature and stationary-point shape, then save it as HTML or GLB.",
    "3D Surface 그래프 HTML 저장": "Save 3D surface as HTML",
    "PowerPoint용 GLB + 3D 범례 저장": "Save GLB with 3D legend for PowerPoint",
    "단일 GLB 파일 안에 표면 색상과 숫자 범례가 함께 들어가며 PowerPoint에서 같이 회전합니다.": "The surface colors and numeric legend are stored in one GLB and rotate together in PowerPoint.",
    "각 요인의 현재값을 움직여 예측 반응과 desirability 변화를 실시간으로 확인합니다. 목표값과 허용범위는 최적 조건 탐색 기준으로 사용됩니다.": "Adjust current factor settings to inspect predicted response and desirability in real time. Target and limits define the optimization objective.",
    "가장 바람직하다고 설정할 목표 반응값입니다.": "Response value defined as most desirable.",
    "허용할 반응값의 하한입니다. 이 값 이하는 desirability가 0입니다.": "Lower acceptable response limit. Desirability is zero at or below this value.",
    "허용할 반응값의 상한입니다. 이 값 이상은 desirability가 0입니다.": "Upper acceptable response limit. Desirability is zero at or above this value.",
    "Lo Limit < Target < Hi Limit 순서가 되도록 입력하세요.": "Enter values in the order Lo Limit < Target < Hi Limit.",
    "Prediction Profiler 실시간 조정 요인": "Live Prediction Profiler factor",
    "Prediction Profiler HTML 저장": "Save Prediction Profiler as HTML",
    "Contour X축": "Contour X axis",
    "Contour Y축": "Contour Y axis",
    "현재 요인 설정에서 모델이 예측한 반응값입니다.": "Response predicted by the model at the current factor settings.",
    "Contour Profiler HTML 저장": "Save Contour Profiler as HTML",
    "실측값과 모델 예측값의 일치도를 비교하고 잔차 분포를 확인합니다. 점들이 기준선에서 체계적으로 벗어나면 모델 또는 이상치를 점검하세요.": "Compare observed and predicted values and inspect residuals. Systematic deviations from the reference line may indicate model issues or outliers.",
    "Predicted Plot HTML 저장": "Save Predicted Plot as HTML",
    "ANOVA로 quadratic 모델 전체의 통계적 유의성을 확인합니다. 동일 조건 반복점이 있으면 순수오차와 lack of fit을 분리해 모델 부족 여부도 검정합니다.": "Use ANOVA to assess overall quadratic-model significance. Replicates allow pure error and lack of fit to be separated.",
    "Lack of fit 표를 만들 수 없습니다.": "A lack-of-fit table cannot be calculated.",
    "적합된 2차 회귀식과 항별 계수를 확인합니다. gradient=0으로 계산한 정상점은 Hessian 고유값으로 최대·최소·안장점을 분류하며 실험범위 밖이면 경고합니다.": "Review the fitted quadratic equation and coefficients. The gradient=0 stationary point is classified from Hessian eigenvalues and flagged when outside the experimental range.",
    "모델 식": "Model equation",
    "계수": "Coefficients",
    "정상점": "Stationary point",
    "정상점이 실험 범위 밖에 있습니다. 외삽 영역의 예측값이므로 해석에 주의하세요.": "The stationary point is outside the experimental range. Interpret this extrapolated prediction cautiously.",
    "정상점 예측 반응값": "Predicted response at stationary point",
    "적합값과 잔차": "Fitted values and residuals",
    "아래 Excel은 각 탭의 계산 데이터를 시트별로 저장합니다. 다운로드 위치는 브라우저 또는 EXE 내부 브라우저의 다운로드 설정을 따릅니다.": "The Excel workbook stores calculations from each tab on separate sheets. The save location follows browser or desktop-app download settings.",
    "RSM 결과 전체 Excel 저장": "Save complete RSM results to Excel",
    "예측 Contour": "Predicted contour",
    "예측 Surface": "Predicted surface",
    "실험점": "Experimental point",
    "관측값": "Observed",
    "예측값": "Predicted",
    "잔차": "Residual",
    "항": "Term",
    "최대점": "Maximum",
    "최소점": "Minimum",
    "안장점": "Saddle point",
    "평탄/약한 곡률": "Flat / weak curvature",
    "판별 불가": "Indeterminate",
    "설계순번": "Standard order",
    "실행순번": "Run",
    "배치번호": "Batch",
    "포인트타입": "Point type",
    "Hessian 고유값": "Hessian eigenvalue",
    "요인": "Factor",
    "정상점 값": "Stationary value",
    "실험 최소": "Experimental min",
    "실험 최대": "Experimental max",
    "범위 내": "Inside range",
    "분류": "Classification",
    "메시지": "Message",
    "값": "Value",
    "인쇄": "Print",
    "실험계획 인쇄": "Print DOE plan",
    "실험계획": "DOE plan",
    "참고사항": "Notes",
    "최소값": "Minimum",
    "최대값": "Maximum",
    "열 너비 조절": "Resize column",
    "국소 최소점": "Local minimum",
    "국소 최대점": "Local maximum",
    "평탄/퇴화 지점": "Flat / degenerate point",
    "gradient=0을 만족하는 고유한 정상점을 계산했습니다.": "A unique stationary point satisfying gradient=0 was calculated.",
    "Hessian이 특이행렬이라 정상점이 고유하지 않습니다. 아래 값은 최소 노름 해입니다.": "The Hessian is singular, so the stationary point is not unique. The values below are the minimum-norm solution.",
    "Hessian이 특이행렬이고 gradient=0 해를 안정적으로 구할 수 없습니다.": "The Hessian is singular and a stable gradient=0 solution could not be obtained.",
    "실측값 vs 예측값": "Observed vs predicted",
    "예측값 vs 잔차": "Predicted vs residual",
    "완전일치선": "Identity line",
    "실측값": "Observed",
    "반복 실험점이 없어 pure error를 계산할 수 없습니다. Lack of fit 검정은 반복점이 있을 때 가능합니다.": "Pure error cannot be calculated because there are no replicated design points. A lack-of-fit test requires replicates.",
    "반복점은 있지만 lack of fit 자유도가 부족합니다. 중심점 외에도 설계 전체의 반복점이 더 필요할 수 있습니다.": "Replicates are present, but there are insufficient degrees of freedom for lack of fit. Additional replicated design points beyond the center may be needed.",
    "Lack of fit p-value가 작으면 현재 quadratic 모델이 데이터 형태를 충분히 설명하지 못할 가능성이 있습니다.": "A small lack-of-fit p-value suggests that the current quadratic model may not adequately describe the data.",
    "Box-Behnken 추정": "Estimated Box-Behnken",
    "CCF 추정": "Estimated CCF",
    "CCI 추정": "Estimated CCI",
    "CCD 추정": "Estimated CCD",
    "중심합성(CCD/CCI) 추정": "Estimated central composite (CCD/CCI)",
    "Full factorial + center 추정": "Estimated full factorial + center",
    "사용자 정의/판별 불가": "Custom / indeterminate",
    "요인 범위가 0인 컬럼이 있어 설계유형을 추정할 수 없습니다.": "The design type cannot be estimated because at least one factor has zero range.",
    "꼭짓점과 중심점은 있으나 축점이 부족해 full quadratic RSM 설계로는 제한적일 수 있습니다.": "Corner and center points are present, but insufficient axial points may limit full quadratic RSM fitting.",
    "점 배치가 표준 CCD, CCF, Box-Behnken 패턴과 명확히 일치하지 않습니다. 그래도 행 수와 rank가 충분하면 RSM 적합은 가능합니다.": "The point pattern does not clearly match a standard CCD, CCF, or Box-Behnken design. RSM fitting is still possible when the row count and rank are sufficient.",
    "CCD는 꼭짓점, 축점, 중심점을 함께 쓰는 대표적인 RSM 설계입니다. 회전성에 유리하지만 축점이 입력한 최소/최대 범위 밖으로 나갈 수 있습니다.": "CCD is a standard RSM design combining corner, axial, and center points. It supports rotatability, but axial points may extend beyond the entered ranges.",
    "CCI는 CCD를 입력 범위 안쪽에 새긴 설계입니다. 축점은 최소/최대에 놓이고, factorial 점은 그보다 안쪽에 배치되어 범위를 넘기지 않습니다.": "CCI inscribes a CCD within the entered ranges. Axial points lie at the minimum and maximum, while factorial points are moved inward.",
    "CCF는 CCD의 face-centered 버전입니다. 축점은 각 요인의 최소/최대 면 중앙에 놓여 실험 범위를 넘기지 않고 수준 해석이 단순합니다.": "CCF is the face-centered form of CCD. Axial points lie at face centers, remain within the experimental ranges, and use simple factor levels.",
    "Box-Behnken은 전체 꼭짓점을 쓰지 않고 두 요인씩 최소/최대 수준으로 바꾸는 설계입니다. 3요인 이상에서 쓸 수 있고 극단 조합을 피하고 싶을 때 유용합니다.": "Box-Behnken varies two factors at their low/high levels without using full corners. It is available for three or more factors and avoids extreme combinations.",
    "Full factorial은 모든 꼭짓점 조합과 중심점을 쓰는 기본 설계입니다. 다만 full quadratic의 제곱항을 안정적으로 추정하려면 CCD/CCF/Box-Behnken이 더 적합합니다.": "Full factorial uses every corner combination plus center points. CCD, CCF, or Box-Behnken is generally better for stable estimation of full quadratic terms.",
    "CCI는 CCD를 입력 범위 안쪽에 넣은 형태입니다. 축점이 최소/최대에 놓이고, factorial 점은 그보다 안쪽에 배치되어 범위를 넘기지 않습니다.": "CCI places a CCD inside the entered ranges. Axial points are at the minimum and maximum, while factorial points are placed inward.",
    "CCF는 CCD의 face-centered 형태입니다. 축점이 각 요인의 최소/최대 면 중앙에 놓여 공정 범위를 넘기기 어려울 때 쓰기 좋습니다.": "CCF is the face-centered form of CCD. Axial points lie at the centers of the minimum and maximum faces, which is useful when the process range must not be exceeded.",
    "Box-Behnken은 전체 꼭짓점을 쓰지 않고 두 요인씩만 높은/낮은 수준으로 바꾸는 설계입니다. 3요인 이상에서 쓸 수 있고 극단 조합을 피하고 싶을 때 유용합니다.": "Box-Behnken varies two factors at high and low levels without using full corners. It is available for three or more factors and helps avoid extreme combinations.",
    "Full factorial은 모든 꼭짓점 조합과 중심점을 보는 기본 설계입니다. 다만 full quadratic의 제곱항을 안정적으로 보려면 CCD/CCF/Box-Behnken이 보통 더 적합합니다.": "Full factorial examines every corner combination plus center points. CCD, CCF, or Box-Behnken is generally better for stable quadratic-term estimation.",
    "Batch당 가능 Run 수는 최소 2 이상이어야 중심점과 설계점을 함께 배치할 수 있습니다.": "Runs available per batch must be at least 2 to place center and design points together.",
    "Batch/중심점 자동 계산이 안전한 범위를 찾지 못했습니다. Batch당 가능 Run 수를 늘려주세요.": "The automatic batch/center-point calculation could not find a valid arrangement. Increase the runs available per batch.",
    "Box-Behnken 설계는 3요인 이상에서 사용합니다.": "Box-Behnken designs require at least three factors.",
    "CSV, XLSX, XLS 파일만 지원합니다.": "Only CSV, XLSX, and XLS files are supported.",
    "GLB로 변환할 표면 삼각형이 없습니다.": "No surface triangles are available for GLB conversion.",
    "상수항": "Intercept",
    "허용영역": "Acceptable region",
    "목표 Contour": "Target contour",
}


REGEX_TRANSLATIONS = [
    (r"^(\d+)요인으로 인식했습니다: (.*)$", r"Detected \1 factors: \2"),
    (r"^외부 CSV의 (\d+)개 행을 사용합니다\. 앞에서 만든 설계의 실험 건수와는 비교하지 않습니다\.$", r"Using \1 rows from the external CSV. The run count is not compared with the generated design."),
    (r"^외부 실험결과 CSV를 읽을 수 없습니다: (.*)$", r"Could not read the external experiment CSV: \1"),
    (r"^분석할 결과 열입니다\. 최대 Y(\d+)까지 선택할 수 있습니다\.$", r"Response columns to analyze. Up to Y\1 can be selected."),
    (r"^(Y\d+) 이름$", r"\1 name"),
    (r"^(X\d+) 이름$", r"\1 name"),
    (r"^(.+) 최소값$", r"\1 minimum"),
    (r"^(.+) 최대값$", r"\1 maximum"),
    (r"^(.+) 최대값은 최소값보다 커야 합니다\.$", r"\1 maximum must be greater than its minimum."),
    (r"^(.+) 고정값$", r"Hold \1 at"),
    (r"^숫자로 변환할 수 없거나 비어 있는 행 (\d+)개를 제외했습니다\.$", r"Excluded \1 rows containing empty or nonnumeric values."),
    (r"^현재 유효 행 (\d+)개입니다\. (\d+)요인 full quadratic 모델에는 최소 (\d+)개가 필요합니다\.$", r"There are \1 valid rows. A \2-factor full quadratic model requires at least \3."),
    (r"^표에서 입력한 Y값 (\d+)개를 반영했습니다\.$", r"Applied \1 Y values entered in the table."),
    (r"^실험표 CSV에서 결과값 (\d+)개를 반영했습니다\.$", r"Imported \1 response values from the DOE worksheet CSV."),
    (r"^표의 (.+) 셀을 선택하고 엑셀 범위를 붙여넣으면 해당 셀부터 행·열 순서대로 바로 입력됩니다\.$", r"Select a \1 cell and paste an Excel range to fill values from that cell in row-column order."),
    (r"^새로 만든 설계의 결과를 입력하는 단계입니다\. 표의 (.+)에 직접 입력·붙여넣거나, 실험계획 CSV에 결과값을 채워 업로드하세요\.$", r"Enter results for the generated design. Type or paste into \1, or upload the DOE plan CSV after filling its response columns."),
    (r"^현재 설계의 결과가 덜 입력되었습니다: (.+)\. 이 설계대로 남은 실험을 완료하거나, 다른 설계에서 얻은 결과라면 페이지 위의 '기존 실험결과 CSV 업로드'에 X값과 Y값을 함께 넣어 주세요\.$", r"Results are incomplete for the current design: \1. Complete the remaining runs, or upload X and Y values together using 'Upload existing experiment CSV' if the data came from another design."),
    (r"^CSV를 읽을 수 없습니다: (.+) 위의 '실험계획 CSV 다운로드' 파일을 사용해 주세요\.$", r"Could not read the CSV: \1 Use the 'Download DOE plan CSV' template above."),
    (r"^2요인 조합의 모서리점과 중심점이 보이고, 전체 꼭짓점은 보이지 않습니다\. 중심점 (\d+)개\.$", r"Pairwise edge points and center points are present without full corners. Center points: \1."),
    (r"^모든 축점과 factorial 꼭짓점이 같은 ±1 수준에 있습니다\. 중심점 (\d+)개\.$", r"All axial and factorial corner points are at the same ±1 level. Center points: \1."),
    (r"^factorial 수준 ±(.+)와 축점 ±1이 보입니다\. 중심점 (\d+)개\.$", r"Factorial levels ±\1 and axial points ±1 are present. Center points: \2."),
    (r"^factorial 수준 ±1과 회전성 축점 ±(.+)가 보입니다\. 중심점 (\d+)개\.$", r"Factorial levels ±1 and rotatable axial points ±\1 are present. Center points: \2."),
    (r"^축점과 factorial 꼭짓점이 함께 있고 중심 거리 수준이 둘 이상입니다\. 입력 범위 정보가 없어 CCD와 CCI는 구분하지 않았습니다\. 중심점 (\d+)개\.$", r"Axial and factorial corner points are present at multiple radial levels. CCD and CCI were not distinguished without range metadata. Center points: \1."),
    (r"^각 Batch에 중심점을 넣기 위해 중심점을 (\d+)개에서 (\d+)개로 자동 보정했습니다\.$", r"Center-point replicates were adjusted from \1 to \2 so every batch includes a center point."),
    (r"^(\d+)요인 full quadratic 모델은 계수 (\d+)개를 추정합니다\.$", r"A \1-factor full quadratic model estimates \2 coefficients."),
]


PHRASE_TRANSLATIONS = [
    ("현재 실험설계와 CSV 양식이 일치하지 않습니다.", "The CSV format does not match the current DOE design."),
    ("위의 '실험계획 CSV 다운로드' 파일에 Y값을 입력해서 다시 불러오세요.", "Enter Y values in the 'Download DOE plan CSV' template and upload it again."),
    ("숫자가 아닌 값이 있습니다.", "contains nonnumeric values."),
    ("실험계획 양식에 숫자 Y값만 입력해 주세요.", "Enter only numeric Y values in the DOE plan."),
    ("누락 열:", "Missing columns:"),
    ("중복 실행순번:", "Duplicate runs:"),
    ("현재 설계에 없는 실행순번:", "Runs not present in the current design:"),
    ("CSV에 실험 행이 없습니다.", "The CSV contains no experiment rows."),
    ("실행순번", "Run"),
    ("현재 설계와 다릅니다.", "does not match the current design."),
    ("입력 현황:", "Completion:"),
    ("CSV에 없는", "Missing from CSV:"),
    ("결과값을 빈칸으로 남겼습니다.", "Response values were left blank."),
    ("지원하지 않습니다.", "is not supported."),
    ("이 앱은 최대 3요인까지 지원합니다.", "This app supports up to three factors."),
    ("이 앱은 Y1~Y6까지만 지원합니다.", "This app supports Y1 through Y6."),
    ("데이터가 없습니다.", "No data was found."),
    ("이름이 같은 열이 중복되어 있습니다.", "Duplicate column names were found."),
    ("X 요인 열을 자동 판별하지 못했습니다.", "X factor columns could not be detected automatically."),
    ("숫자 Y 결과 열을 찾지 못했습니다.", "No numeric Y response column was found."),
    ("중심점", "center point"),
    ("예측 Contour", "Predicted contour"),
    ("예측 Surface", "Predicted surface"),
    ("허용영역", "Acceptable region"),
    ("목표 Contour", "Target contour"),
    ("꼭짓점", "corner points"),
    ("축점", "axial points"),
    ("설계", "design"),
]


def set_language(language: str) -> str:
    normalized = language if language in LANGUAGE_LABELS else "ko"
    _LANGUAGE.set(normalized)
    return normalized


def get_language() -> str:
    return _LANGUAGE.get()


def is_english() -> bool:
    return get_language() == "en"


def settings_path() -> Path:
    portable_dir = os.environ.get("RSM_PORTABLE_DATA_DIR")
    if portable_dir:
        return Path(portable_dir) / "settings.json"
    app_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DOE RSM"
    return app_dir / "settings.json"


def load_preferred_language() -> str | None:
    path = settings_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    language = payload.get("language")
    return language if language in LANGUAGE_LABELS else None


def save_preferred_language(language: str) -> None:
    normalized = set_language(language)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"language": normalized}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def t(value: Any) -> Any:
    if not is_english() or not isinstance(value, str):
        return value
    translated = ENGLISH.get(value)
    if translated is not None:
        return translated
    translated = value
    for pattern, replacement in REGEX_TRANSLATIONS:
        if re.search(pattern, translated):
            translated = re.sub(pattern, replacement, translated)
            break
    for source, replacement in PHRASE_TRANSLATIONS:
        translated = translated.replace(source, replacement)
    return translated


def localize_plotly_figure(figure: Any) -> Any:
    if not is_english() or not hasattr(figure, "to_plotly_json"):
        return figure
    try:
        import plotly.graph_objects as go

        def walk(value: Any) -> Any:
            if isinstance(value, str):
                return t(value)
            if isinstance(value, dict):
                return {key: walk(item) for key, item in value.items()}
            if isinstance(value, list):
                return [walk(item) for item in value]
            if isinstance(value, tuple):
                return tuple(walk(item) for item in value)
            return value

        return go.Figure(walk(figure.to_plotly_json()))
    except Exception:
        return figure


_TEXT_METHODS = {
    "title",
    "header",
    "subheader",
    "caption",
    "info",
    "warning",
    "error",
    "success",
    "toast",
    "button",
    "download_button",
    "file_uploader",
    "text_input",
    "text_area",
    "number_input",
    "slider",
    "toggle",
    "checkbox",
    "selectbox",
    "radio",
    "multiselect",
    "segmented_control",
    "pills",
    "metric",
    "expander",
    "popover",
    "markdown",
    "write",
}
_SELECTION_METHODS = {"selectbox", "radio", "multiselect", "segmented_control", "pills"}


def _translated_format_func(existing: Callable[[Any], Any] | None) -> Callable[[Any], Any]:
    def format_option(option: Any) -> str:
        formatted = existing(option) if existing is not None else option
        return str(t(formatted))

    return format_option


def _wrap_streamlit_method(name: str, original: Callable[..., Any], label_index: int) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        mutable_args = list(args)
        if name == "plotly_chart":
            if len(mutable_args) > label_index:
                mutable_args[label_index] = localize_plotly_figure(mutable_args[label_index])
            return original(*mutable_args, **kwargs)
        if name == "tabs":
            if len(mutable_args) > label_index:
                mutable_args[label_index] = [t(label) for label in mutable_args[label_index]]
            if isinstance(kwargs.get("default"), str):
                kwargs["default"] = t(kwargs["default"])
            return original(*mutable_args, **kwargs)
        if len(mutable_args) > label_index and isinstance(mutable_args[label_index], str):
            mutable_args[label_index] = t(mutable_args[label_index])
        for key in ("help", "placeholder"):
            if isinstance(kwargs.get(key), str):
                kwargs[key] = t(kwargs[key])
        if name in _SELECTION_METHODS:
            existing = kwargs.get("format_func")
            kwargs["format_func"] = _translated_format_func(existing)
        return original(*mutable_args, **kwargs)

    wrapped.__name__ = getattr(original, "__name__", name)
    wrapped.__doc__ = getattr(original, "__doc__", None)
    return wrapped


def install_streamlit_translation() -> None:
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator

    if getattr(st, "_rsm_i18n_installed", False):
        return

    method_names = sorted(_TEXT_METHODS | {"tabs", "plotly_chart"})
    for name in method_names:
        module_method = getattr(st, name, None)
        if callable(module_method):
            setattr(st, name, _wrap_streamlit_method(name, module_method, 0))
        generator_method = getattr(DeltaGenerator, name, None)
        if callable(generator_method):
            setattr(
                DeltaGenerator,
                name,
                _wrap_streamlit_method(name, generator_method, 1),
            )
    st._rsm_i18n_installed = True
