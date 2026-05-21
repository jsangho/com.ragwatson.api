from titanic.app.schemas.passenger_schema import PassengerSchema
from titanic.app.schemas.problem_definition import FEATURE_COLUMNS, TARGET_COLUMN


def validate_passenger_schema(passenger: PassengerSchema) -> list[str]:
    """단일 승객 레코드 검증. 오류 메시지 목록을 반환합니다."""
    errors: list[str] = []

    if passenger.Survived is not None and passenger.Survived not in (0, 1):
        errors.append(f"{TARGET_COLUMN}는 0(사망) 또는 1(생존)이어야 합니다.")

    if passenger.Pclass is not None and passenger.Pclass not in (1, 2, 3):
        errors.append("Pclass는 1, 2, 3 중 하나여야 합니다.")

    if passenger.Sex is not None and passenger.Sex not in ("male", "female"):
        errors.append("Sex는 male 또는 female이어야 합니다.")

    if passenger.Age is not None and (passenger.Age < 0 or passenger.Age > 120):
        errors.append("Age는 0~120 범위여야 합니다.")

    if passenger.SibSp is not None and passenger.SibSp < 0:
        errors.append("SibSp는 0 이상이어야 합니다.")

    if passenger.Parch is not None and passenger.Parch < 0:
        errors.append("Parch는 0 이상이어야 합니다.")

    if passenger.Embarked is not None and passenger.Embarked not in ("C", "Q", "S"):
        errors.append("Embarked는 C, Q, S 중 하나여야 합니다.")

    return errors


def validate_feature_columns(columns: list[str]) -> list[str]:
    """학습용 데이터프레임에 독립변수·타깃 컬럼이 있는지 확인합니다."""
    errors: list[str] = []
    missing_features = [c for c in FEATURE_COLUMNS if c not in columns]
    if missing_features:
        errors.append(f"독립변수 컬럼 누락: {', '.join(missing_features)}")
    if TARGET_COLUMN not in columns:
        errors.append(f"타깃 컬럼 누락: {TARGET_COLUMN}")
    return errors
