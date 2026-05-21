from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from titanic.app.models.passenger_model import PassengerModel
from titanic.app.schemas.passenger_schema import PassengerSchema

logger = LAYER_LOG

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CSV_PATH = _DATA_DIR / "Titanic-Dataset.csv"


class PassengerRepository:
    """CSV 데이터 접근 및 Neon Postgres 적재."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db

    def _read_csv(self) -> pd.DataFrame:
        return pd.read_csv(_CSV_PATH)

    def get_sample_row(self) -> pd.DataFrame:
        df = self._read_csv()
        return df.iloc[[0]].astype(object).where(df.iloc[[0]].notna(), None)

    def get_count(self) -> int:
        return int(self._read_csv().shape[0])

    def get_survived_count(self) -> int:
        df = self._read_csv()
        return int((df["Survived"] == 1).sum())

    def get_dead_count(self) -> int:
        df = self._read_csv()
        return int((df["Survived"] == 0).sum())

    def get_dataframe(self) -> pd.DataFrame:
        """학습·검증·Neon 적재용 전체 데이터프레임."""
        return self._read_csv()

    @staticmethod
    def schema_to_orm(passenger: PassengerSchema) -> PassengerModel:
        return PassengerModel(
            passenger_id=passenger.PassengerId or 0,
            survived=passenger.Survived,
            pclass=passenger.Pclass,
            name=passenger.Name,
            sex=passenger.Sex,
            age=passenger.Age,
            sibsp=passenger.SibSp,
            parch=passenger.Parch,
            ticket=passenger.Ticket,
            fare=passenger.Fare,
            cabin=passenger.Cabin,
            embarked=passenger.Embarked,
        )

    async def _flush_to_neon(self) -> None:
        if self.db is None:
            raise RuntimeError("Neon 세션이 필요합니다.")
        await self.db.flush()

    async def count_in_neon(self) -> int:
        if self.db is None:
            return 0
        result = await self.db.execute(select(func.count()).select_from(PassengerModel))
        return int(result.scalar_one())

    async def save_passenger(self, passenger: PassengerSchema) -> PassengerModel:
        if self.db is None:
            raise RuntimeError("Neon 세션이 필요합니다.")
        logger.info(
            "[PassengerRepository] save_passenger -> Neon — passengerId=%s",
            passenger.PassengerId,
        )
        row = self.schema_to_orm(passenger)
        self.db.add(row)
        await self._flush_to_neon()
        await self.db.refresh(row)
        logger.info(
            "[PassengerRepository] save_passenger <- Neon — passengerId=%s, db_id=%s",
            passenger.PassengerId,
            row.id,
        )
        return row
