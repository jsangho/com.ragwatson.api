from sqlalchemy.ext.asyncio import AsyncSession

from database import APP_LOGGER
from secom.app.models.user_model import UserModel
from secom.app.schemas.user_schema import UserSchema
from secom.app.services.user_service import UserService

logger = APP_LOGGER


class UserController(object):
    def __init__(self, db: AsyncSession) -> None:
        self.user_service = UserService(db)

    async def save_user(self, user_schema: UserSchema) -> None:
        logger.info(
            "[UserController] save_user 레이어 완료 — userId=%s",
            user_schema.login_id,
        )
        await self.user_service.save_user(user_schema)

    async def login_user(self, login_id: str, password: str) -> UserModel:
        logger.info(
            "[UserController] login_user 레이어 완료 — userId=%s",
            login_id,
        )
        return await self.user_service.login_user(login_id, password)
