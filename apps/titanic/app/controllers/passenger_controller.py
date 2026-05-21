from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from titanic.app.schemas.passenger_schema import PassengerSchema
from titanic.app.services.passenger_service import PassengerService

logger = LAYER_LOG


class PassengerController:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self.passenger_service = PassengerService(db)

    def get_problem_summary(self) -> str:
        return self.passenger_service.get_problem_summary()

    def get_data(self):
        logger.info("[PassengerController] get_data -> Service")
        return self.passenger_service.get_data()

    def get_count(self) -> int:
        return self.passenger_service.get_count()

    def get_survived_count(self) -> int:
        return self.passenger_service.get_survived_count()

    def get_dead_count(self) -> int:
        return self.passenger_service.get_dead_count()

    def get_model_name_and_accuracy(self) -> str:
        logger.info("[PassengerController] get_model_name -> Service")
        return self.passenger_service.get_model_name()

    def has_decision_tree_model(self) -> bool:
        return self.passenger_service.has_decision_tree_model()

    async def save_passenger(self, passenger: PassengerSchema) -> None:
        logger.info(
            "[PassengerController] save_passenger -> Service — passengerId=%s",
            passenger.PassengerId,
        )
        await self.passenger_service.save_passenger(passenger)
        logger.info(
            "[PassengerController] save_passenger <- Service — passengerId=%s",
            passenger.PassengerId,
        )
