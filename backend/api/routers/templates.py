from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services import templates
from api.api_services.errors import ServiceError
from api.dependencies.authenticate import get_current_user_claims
from api.type_models.templates import TemplateCreate, TemplateOut, TemplateUpdate
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db

router = APIRouter(
    prefix="/templates",
    tags=["templates"],
)


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> list[TemplateOut]:
    return await templates.list_for(db, claims.user_id)


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(
    req: TemplateCreate,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> TemplateOut:
    return await templates.create(db, claims.user_id, req)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    req: TemplateUpdate,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> TemplateOut:
    try:
        return await templates.update(db, claims.user_id, template_id, req)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    claims: UserClaims = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    await templates.delete(db, claims.user_id, template_id)
    return Response(status_code=204)
