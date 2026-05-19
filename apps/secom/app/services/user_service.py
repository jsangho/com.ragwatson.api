from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import APP_LOGGER
from secom.app.repositories.user_repository import UserRepository
from secom.app.schemas.user_schema import UserSchema
from secom.app.security.password import hash_password, verify_password

logger = APP_LOGGER


class UserService(object):
    def __init__(self, db: AsyncSession) -> None:
        self.user_repository = UserRepository(db)

    async def save_user(self, user_schema: UserSchema) -> None:
        logger.info(
            "[UserService] save_user 레이어 완료 — userId=%s",
            user_schema.login_id,
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
        await self.user_repository.save_user(user_schema, password_hash)

    async def login_user(self, login_id: str, password: str):
        logger.info("[UserService] login_user 레이어 완료 — userId=%s", login_id)
        user = await self.user_repository.find_by_login_id(login_id)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="ID 또는 비밀번호가 올바르지 않습니다.",
            )
        return user
