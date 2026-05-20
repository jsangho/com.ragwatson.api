from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from secom.app.models.user_model import UserModel
from secom.app.schemas.user_schema import UserSchema
from secom.app.services.user_service import UserService

logger = LAYER_LOG


class UserController(object):
    def __init__(self, db: AsyncSession) -> None:
        self.user_service = UserService(db)

    async def save_user(self, user_schema: UserSchema) -> None:
        logger.info(
            "[UserController] save_user -> Service — userId=%s, email=%s",
            user_schema.login_id,
            user_schema.email,
        )
        await self.user_service.save_user(user_schema)
        logger.info(
            "[UserController] save_user <- Service — userId=%s",
            user_schema.login_id,
        )

    async def login_user(self, login_id: str, password: str) -> UserModel:
        logger.info(
            "[UserController] login_user -> Service — userId=%s",
            login_id,
        )
        user = await self.user_service.login_user(login_id, password)
        logger.info(
            "[UserController] login_user <- Service — userId=%s, user=%s",
            login_id,
            user.to_log_dict(),
        )
        return user
