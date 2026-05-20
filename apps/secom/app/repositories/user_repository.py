from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from secom.app.models.user_model import UserModel
from secom.app.schemas.user_schema import UserSchema

logger = LAYER_LOG


class UserRepository(object):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _flush_to_neon(self) -> None:
        """변경 사항을 세션에 반영합니다 (commit은 get_db에서 처리)."""
        await self.db.flush()

    async def find_by_email(self, email: str) -> UserModel | None:
        logger.info(
            "[UserRepository] find_by_email -> Neon — email=%s",
            email,
        )
        result = await self.db.execute(
            select(UserModel).where(UserModel.email == email)
        )
        user = result.scalar_one_or_none()
        if user is None:
            logger.info(
                "[UserRepository] find_by_email <- Neon — email=%s, user=없음",
                email,
            )
        else:
            logger.info(
                "[UserRepository] find_by_email <- Neon — email=%s, user=%s",
                email,
                user.to_log_dict(),
            )
        return user

    async def find_by_login_id(self, login_id: str) -> UserModel | None:
        logger.info(
            "[UserRepository] find_by_login_id -> Neon — userId=%s",
            login_id,
        )
        result = await self.db.execute(
            select(UserModel).where(UserModel.login_id == login_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            logger.info(
                "[UserRepository] find_by_login_id <- Neon — userId=%s, user=없음",
                login_id,
            )
        else:
            logger.info(
                "[UserRepository] find_by_login_id <- Neon — userId=%s, user=%s",
                login_id,
                user.to_log_dict(),
            )
        return user

    async def save_user(self, user_schema: UserSchema, password_hash: str) -> UserModel:
        logger.info(
            "[UserRepository] save_user -> Neon — userId=%s, email=%s",
            user_schema.login_id,
            user_schema.email,
        )
        user = UserModel(
            login_id=user_schema.login_id,
            nickname=user_schema.nickname,
            email=user_schema.email,
            password_hash=password_hash,
            role=user_schema.role,
        )
        self.db.add(user)
        await self._flush_to_neon()
        await self.db.refresh(user)
        logger.info(
            "[UserRepository] save_user <- Neon — userId=%s, db_id=%s, user=%s",
            user_schema.login_id,
            user.id,
            user.to_log_dict(),
        )
        return user
