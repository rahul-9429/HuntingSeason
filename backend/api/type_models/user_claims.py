from pydantic import BaseModel, EmailStr


class UserClaims(BaseModel):
    user_id: int
    user_email: EmailStr
