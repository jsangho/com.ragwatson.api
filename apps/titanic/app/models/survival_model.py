from sklearn.tree import DecisionTreeClassifier


class SurvivalModel:
    """생존 예측용 머신러닝 모델 (scikit-learn DecisionTree)."""

    def __init__(self) -> None:
        self.model = DecisionTreeClassifier()

    def get_model_name(self) -> str:
        return type(self.model).__name__

    @property
    def is_ready(self) -> bool:
        return self.model is not None
