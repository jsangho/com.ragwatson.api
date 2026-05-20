import asyncio

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from secom.app.repositories.user_repository import UserRepository
from secom.app.schemas.user_schema import UserSchema
from secom.app.security.password import hash_password, verify_password

logger = LAYER_LOG


class UserService(object):
    def __init__(self, db: AsyncSession) -> None:
        self.user_repository = UserRepository(db)

    async def save_user(self, user_schema: UserSchema) -> None:
        logger.info(
            "[UserService] save_user -> Repository — userId=%s, email=%s",
            user_schema.login_id,
            user_schema.email,
        )
        if user_schema.password != user_schema.password_confirm:
            raise HTTPException(
                status_code=400,
                detail="비밀번호와 비밀번호 확인이 일치하지 않습니다.",
            )

        if await self.user_repository.find_by_email(user_schema.email):
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")

        if await self.user_repository.find_by_login_id(user_schema.login_id):
            raise HTTPException(status_code=409, detail="이미 사용 중인 ID입니다.")

        password_hash = hash_password(user_schema.password)
        user = await self.user_repository.save_user(user_schema, password_hash)
        logger.info(
            "[UserService] save_user <- Repository — userId=%s, db_id=%s",
            user_schema.login_id,
            user.id,
        )

    async def login_user(self, login_id: str, password: str):
        logger.info(
            "[UserService] login_user -> Repository — userId=%s",
            login_id,
        )
        user = await self.user_repository.find_by_login_id(login_id)
        password_ok = await asyncio.to_thread(
            verify_password, password, user.password_hash if user else ""
        )
        if user is None or not password_ok:
            logger.info(
                "[UserService] login_user <- Repository — userId=%s, user=인증실패",
                login_id,
            )
            raise HTTPException(
                status_code=401,
                detail="ID 또는 비밀번호가 올바르지 않습니다.",
            )
        logger.info(
            "[UserService] login_user <- Repository — userId=%s, user=%s",
            login_id,
            user.to_log_dict(),
        )
        return user
