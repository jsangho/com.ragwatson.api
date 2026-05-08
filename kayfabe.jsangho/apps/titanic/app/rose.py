from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import joblib
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.tree import DecisionTreeClassifier
except Exception as e:  # pragma: no cover
    _SKLEARN_IMPORT_ERROR = e
else:  # pragma: no cover
    _SKLEARN_IMPORT_ERROR = None


_DATA_DIR = Path(__file__).resolve().parent
_CSV_PATH = _DATA_DIR / "Titanic-Dataset.csv"
_MODEL_PATH = _DATA_DIR / "titanic_decision_tree.joblib"


class Rose:
    def __init__(self):
        pass

    def train_and_save_decision_tree(
        self,
        csv_path: Path | str = _CSV_PATH,
        model_path: Path | str = _MODEL_PATH,
        random_state: int = 42,
    ):
        if _SKLEARN_IMPORT_ERROR is not None:
            raise RuntimeError(
                "scikit-learn/joblib이 설치되어 있지 않습니다. "
                "`pip install scikit-learn joblib` 후 다시 실행하세요."
            ) from _SKLEARN_IMPORT_ERROR

        csv_path = Path(csv_path)
        model_path = Path(model_path)

        df = pd.read_csv(csv_path)

        target = "Survived"
        feature_cols = [
            "Pclass",
            "Sex",
            "Age",
            "SibSp",
            "Parch",
            "Fare",
            "Embarked",
        ]

        X = df[feature_cols]
        y = df[target].astype(int)

        numeric_features = ["Pclass", "Age", "SibSp", "Parch", "Fare"]
        categorical_features = ["Sex", "Embarked"]

        numeric_transformer = Pipeline(
            steps=[("imputer", SimpleImputer(strategy="median"))]
        )
        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]
        )

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, numeric_features),
                ("cat", categorical_transformer, categorical_features),
            ]
        )

        model = DecisionTreeClassifier(random_state=random_state)

        clf = Pipeline(steps=[("preprocess", preprocessor), ("model", model)])

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=random_state, stratify=y
        )
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)
        acc = float(accuracy_score(y_test, y_pred))

        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(clf, model_path)

        return {
            "model_path": str(model_path),
            "accuracy": acc,
            "rows": int(len(df)),
        }


if __name__ == "__main__":  # run training locally
    r = Rose()
    print(r.train_and_save_decision_tree())

