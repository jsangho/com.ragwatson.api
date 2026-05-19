from pydantic import BaseModel


class UserSchema(BaseModel):
    login_id: str
    nickname: str
    email: str
    password: str
    password_confirm: str
    role: str
