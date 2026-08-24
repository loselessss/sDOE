from __future__ import annotations

from rsm_i18n import is_english, t

APP_BUILD_VERSION = "2026.08.24-v64"
RESPONSE_COLUMNS = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6"]

TERM_HELP = {
    "RSM": "Response Surface Methodology. 여러 요인과 반응값의 관계를 2차 회귀식으로 적합해 최적 조건과 곡률을 탐색하는 방법입니다.",
    "CCD": "Central Composite Design. 꼭짓점·축점·중심점을 사용합니다. 회전성에 유리하지만 축점이 설정한 최소·최대 범위 밖에 놓일 수 있습니다.",
    "CCI": "Central Composite Inscribed. 축점을 최소·최대 범위에 두고 factorial 점을 안쪽으로 축소한 CCD 계열 설계입니다.",
    "CCF": "Central Composite Face-centered. 축점이 요인 범위의 각 면 중앙에 놓이며 모든 실험점이 설정 범위 안에 있습니다.",
    "Box-Behnken": "전체 꼭짓점을 사용하지 않고 요인 두 개씩 저·고수준으로 바꾸는 3요인 이상 RSM 설계입니다.",
    "Full factorial": "각 요인의 저·고수준 조합을 모두 실험하는 설계입니다. 중심점을 추가해도 제곱항 추정은 약할 수 있습니다.",
    "Run": "실제로 수행하는 개별 실험 한 회입니다.",
    "Batch": "같은 작업 시기나 조건으로 묶어 수행하는 실험 묶음입니다. Batch별 중심점은 Batch 내부 오차 확인에 도움이 됩니다.",
    "중심점": "모든 요인을 범위 중앙에 둔 반복 실험점입니다. 순수오차와 곡률을 추정하는 데 사용합니다.",
    "seed": "난수 생성의 시작값입니다. 같은 seed를 쓰면 같은 랜덤 실험순서를 다시 만들 수 있습니다.",
    "Point type": "설계점의 역할입니다. Design은 꼭짓점·축점 등의 설계점이고 Center는 중심점입니다.",
    "StdOrder": "설계법에서 정한 표준 순번입니다. 랜덤화 전의 정석 설계점 배열을 확인할 때 사용합니다.",
    "coded": "요인값을 중심 0과 일정한 척도로 변환한 값입니다. 서로 단위가 다른 요인을 같은 기준으로 비교할 때 사용합니다.",
    "Contour": "두 요인의 조합에 대한 예측 반응값을 같은 값끼리 선으로 연결한 등고선도입니다.",
    "3D Surface": "두 요인의 조합에 따른 예측 반응값을 높이와 색으로 표현한 3차원 반응표면입니다.",
    "Prediction Profiler": "다른 요인을 고정한 상태에서 한 요인의 변화가 예측 반응에 미치는 영향을 보여주는 그래프입니다.",
    "Contour Profiler": "목표 반응 범위와 현재 요인 설정을 등고선 위에서 함께 확인하는 최적화 도구입니다.",
    "Predicted Plot": "실측값과 모델 예측값 및 잔차를 비교해 적합 상태와 이상 패턴을 확인하는 진단 그래프입니다.",
    "ANOVA": "Analysis of Variance. 회귀모델이 데이터 변동을 통계적으로 유의하게 설명하는지 검정합니다.",
    "Lack of fit": "반복점의 순수오차와 모델 잔차를 비교하는 검정입니다. p-value가 작으면 현재 모델 형태가 부족할 가능성이 있습니다.",
    "R²": "모델이 반응값 변동을 설명하는 비율입니다. 1에 가까울수록 설명력이 높지만 이것만으로 모델 적합성을 판단하지는 않습니다.",
    "Adjusted R²": "항의 개수와 표본 수를 보정한 R²입니다. 불필요한 항을 추가했을 때 생기는 R² 상승을 완화합니다.",
    "정상점": "적합된 반응표면에서 모든 요인 방향의 기울기가 0이 되는 점입니다. 최대점·최소점·안장점일 수 있습니다.",
    "Hessian": "2차 미분으로 구성된 행렬입니다. 고유값 부호를 이용해 정상점을 최대·최소·안장점으로 분류합니다.",
    "Desirability": "예측값이 목표와 제한을 얼마나 만족하는지 나타내는 0~1 점수입니다. 1에 가까울수록 목표에 적합합니다.",
    "유효 행": "선택한 모든 X와 Y가 숫자로 채워져 실제 모델 적합에 사용된 행 수입니다.",
    "설계 추정": "입력된 요인점 배치를 기준으로 앱이 추정한 실험설계 종류입니다.",
}

TERM_HELP_EN = {
    "RSM": "Response Surface Methodology. Fits a quadratic regression model to explore factor-response relationships, curvature, and optimum settings.",
    "CCD": "Central Composite Design. Uses factorial, axial, and center points. It supports rotatability, but axial points may exceed the entered factor ranges.",
    "CCI": "Central Composite Inscribed. Places axial points at the entered limits and scales factorial points inward.",
    "CCF": "Central Composite Face-centered. Places axial points at the center of each factor-range face so every run remains inside the entered ranges.",
    "Box-Behnken": "An RSM design for three or more factors that varies two factors at a time without using all extreme corners.",
    "Full factorial": "Tests every low/high factor combination. Adding center points alone may still provide weak quadratic-term estimation.",
    "Run": "One individual experiment performed in the actual execution sequence.",
    "Batch": "A group of runs performed under the same period or operating condition. Center points in each batch help assess within-batch error.",
    "중심점": "A replicated run with every factor at its midpoint. Center points support pure-error and curvature estimation.",
    "seed": "The starting value for randomization. Reusing a seed reproduces the same randomized run order.",
    "Point type": "The role of a design point. Design indicates factorial or axial points, while Center indicates center points.",
    "StdOrder": "The canonical order defined by the design before run-order randomization.",
    "coded": "A scaled factor value with the center at 0. Coding allows factors with different units to be compared on a common scale.",
    "Contour": "A two-dimensional plot joining factor combinations with equal predicted response values.",
    "3D Surface": "A three-dimensional response surface that uses height and color to show predicted response values.",
    "Prediction Profiler": "Shows how each factor changes the predicted response while other factors are held at current settings.",
    "Contour Profiler": "An optimization view combining response limits, contours, and current factor settings.",
    "Predicted Plot": "Compares observed values, model predictions, and residuals to assess fit and unusual patterns.",
    "ANOVA": "Analysis of Variance. Tests whether the regression model explains a statistically significant portion of response variation.",
    "Lack of fit": "Compares model residuals with pure error from replicated settings. A small p-value may indicate an inadequate model form.",
    "R²": "The proportion of response variation explained by the model. A high value alone does not guarantee an adequate model.",
    "Adjusted R²": "R² adjusted for sample size and number of model terms, reducing artificial gains from unnecessary terms.",
    "정상점": "A point where the fitted response-surface gradient is zero. It may be a maximum, minimum, or saddle point.",
    "Hessian": "The matrix of second derivatives. Eigenvalue signs classify the stationary point as a maximum, minimum, or saddle point.",
    "Desirability": "A 0-to-1 score indicating how well a predicted response meets the target and limits. Values near 1 are more desirable.",
    "유효 행": "Rows with numeric values in every selected X and Y column and therefore used for model fitting.",
    "설계 추정": "The design type inferred from the arrangement of factor settings in the input data.",
}


def term_help(*terms: str) -> str:
    source = TERM_HELP_EN if is_english() else TERM_HELP
    return "\n\n".join(
        f"**{t(term)}**: {source[term]}"
        for term in terms
        if term in source
    )
