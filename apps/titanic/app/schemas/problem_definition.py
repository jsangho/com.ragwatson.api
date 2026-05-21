"""타이타닉 생존 예측 — 이진 분류 문제 정의."""

# 종속변수 (예측 대상): Survived (0=사망, 1=생존)
TARGET_COLUMN = "Survived"

# 독립변수 6개 — 생존 유무를 예측하는 데 사용하는 주요 특성
FEATURE_COLUMNS = ("Pclass", "Sex", "Age", "SibSp", "Parch", "Fare")

# 명단·분석용 보조 컬럼 (Kaggle CSV 기준; Boat는 원본에 없음)
AUXILIARY_COLUMNS = ("PassengerId", "Name", "Ticket", "Cabin", "Embarked")

PROBLEM_SUMMARY = (
    "1912년 타이타닉 탑승자 명단을 바탕으로, "
    "6개 독립변수(Pclass, Sex, Age, SibSp, Parch, Fare)로 "
    "생존 여부(Survived: 0=사망, 1=생존)를 예측하는 이진 분류 문제"
)
