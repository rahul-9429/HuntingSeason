from typing import Optional

from sqlalchemy import delete as sql_delete
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.errors import ServiceError
from api.type_models.templates import TemplateCreate, TemplateOut, TemplateUpdate
from models.email_template import EmailTemplate

_REQUIRED = ("name", "subject", "body_html", "skip_ai", "is_default")
_CONTENT = ("name", "subject", "body_html", "signature_html", "sender_name", "skip_ai")


async def _clear_default(db: AsyncSession, user_id: int, keep: Optional[int] = None) -> None:
    query = sql_update(EmailTemplate).where(
        EmailTemplate.user_id == user_id, EmailTemplate.is_default.is_(True)
    )
    if keep is not None:
        query = query.where(EmailTemplate.id != keep)
    await db.execute(query.values(is_default=False))


async def _get(db: AsyncSession, user_id: int, template_id: int) -> EmailTemplate:
    template = await db.scalar(
        select(EmailTemplate).where(EmailTemplate.id == template_id, EmailTemplate.user_id == user_id)
    )
    if template is None:
        raise ServiceError("Template not found", status_code=404)
    return template


async def list_for(db: AsyncSession, user_id: int) -> list[TemplateOut]:
    templates = await db.scalars(
        select(EmailTemplate)
        .where(EmailTemplate.user_id == user_id)
        .order_by(EmailTemplate.is_default.desc(), EmailTemplate.created_at)
    )
    return [TemplateOut.model_validate(template) for template in templates]


async def _has_default(db: AsyncSession, user_id: int) -> bool:
    return bool(
        await db.scalar(
            select(EmailTemplate.id).where(
                EmailTemplate.user_id == user_id, EmailTemplate.is_default.is_(True)
            )
        )
    )


async def create(db: AsyncSession, user_id: int, req: TemplateCreate) -> TemplateOut:
    values = req.model_dump()
    if not values["is_default"] and not await _has_default(db, user_id):
        values["is_default"] = True
    if values["is_default"]:
        await _clear_default(db, user_id)
    template = EmailTemplate(user_id=user_id, **values)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateOut.model_validate(template)


async def update(
    db: AsyncSession, user_id: int, template_id: int, req: TemplateUpdate
) -> TemplateOut:
    template = await _get(db, user_id, template_id)
    changes = req.model_dump(exclude_unset=True)
    if any(changes.get(field, "") is None for field in _REQUIRED):
        raise ServiceError("Only signature_html and sender_name can be cleared", status_code=422)
    if changes.get("is_default"):
        await _clear_default(db, user_id, keep=template_id)
    if any(field in changes for field in _CONTENT):
        template.is_generated = False
    for field, value in changes.items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template)
    return TemplateOut.model_validate(template)


async def delete(db: AsyncSession, user_id: int, template_id: int) -> None:
    was_default = await db.scalar(
        select(EmailTemplate.is_default).where(
            EmailTemplate.id == template_id, EmailTemplate.user_id == user_id
        )
    )
    await db.execute(
        sql_delete(EmailTemplate).where(
            EmailTemplate.id == template_id, EmailTemplate.user_id == user_id
        )
    )
    if was_default:
        replacement = await db.scalar(
            select(EmailTemplate)
            .where(EmailTemplate.user_id == user_id)
            .order_by(EmailTemplate.created_at, EmailTemplate.id)
            .limit(1)
        )
        if replacement is not None:
            replacement.is_default = True
    await db.commit()
