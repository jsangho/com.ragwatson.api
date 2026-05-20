from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, SQLModel

from database import Base


class UserModel(SQLModel, table=True):
    """users 테이블. PK 규칙: docs/DevOps/Backend/ENTITY_RULE.md"""

    __tablename__ = "users"
    metadata = Base.metadata

    # 시스템 내부용 자동 증감 고유 번호 (기본 키)
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"name": "id"},
    )
    login_id: Optional[str] = Field(
        default=None,
        max_length=50,
        sa_column=Column(String(50), unique=True, nullable=True, index=True),
    )
    nickname: str = Field(max_length=50)
    email: str = Field(
        max_length=255,
        sa_column=Column(String(255), unique=True, nullable=False, index=True),
    )
    password_hash: str = Field(
        sa_column=Column("password", String(255), nullable=False),
    )
    role: str = Field(default="user", max_length=20)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    def to_log_dict(self) -> dict:
        return {
            "id": self.id,
            "login_id": self.login_id,
            "nickname": self.nickname,
            "email": self.email,
            "role": self.role,
        }
