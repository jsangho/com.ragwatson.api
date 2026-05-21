from typing import Optional

from pydantic import BaseModel, Field


class PassengerSchema(BaseModel):
    """타이타닉 탑승자 1명 — Kaggle Titanic-Dataset.csv 컬럼 매핑."""

    PassengerId: Optional[int] = Field(None, description="승객 ID")
    Survived: Optional[int] = Field(
        None, description="생존 여부 (0 = 사망, 1 = 생존) — 이진 분류 타깃"
    )
    Pclass: Optional[int] = Field(
        None, description="티켓 클래스 (1 = 1등석, 2 = 2등석, 3 = 3등석)"
    )
    Name: Optional[str] = Field(None, description="이름")
    Sex: Optional[str] = Field(None, description="성별 (male / female)")
    Age: Optional[float] = Field(None, description="나이")
    SibSp: Optional[int] = Field(
        None, description="함께 탑승한 형제·배우자 수"
    )
    Parch: Optional[int] = Field(
        None, description="함께 탑승한 부모·자녀 수"
    )
    Ticket: Optional[str] = Field(None, description="티켓 번호")
    Fare: Optional[float] = Field(None, description="탑승 요금")
    Cabin: Optional[str] = Field(None, description="객실 번호")
    Boat: Optional[str] = Field(
        None,
        description="탈출 보트 번호 (확장 필드; Kaggle CSV에는 없음)",
    )
    Embarked: Optional[str] = Field(
        None,
        description="승선 항구 (C=Cherbourg, Q=Queenstown, S=Southampton)",
    )
