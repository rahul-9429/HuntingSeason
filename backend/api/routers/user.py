from fastapi import APIRouter, Depends

from api.dependencies.authenticate import get_current_user_claims
from api.type_models.user_claims import UserClaims

router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@router.get("/me", response_model=UserClaims)
async def get_me(claims: UserClaims = Depends(get_current_user_claims)) -> UserClaims:
    """Who the token belongs to. The first call after sign-up creates the user."""
    return claims
