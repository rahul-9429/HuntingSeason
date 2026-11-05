import argparse
import asyncio
import hashlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(override=True)

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.session import AsyncSessionLocal, async_engine
from models.company import Company
from models.contact import Contact
from models.email_template import EmailTemplate
from models.enums import OutreachStage
from models.user import User
from models.user_company import UserCompany
from models.user_contact import UserContact

logger = logging.getLogger("seed_demo_leads")

PEOPLE = [
    ("Priya", "Sharma", "Engineering Manager", "hiring_manager"),
    ("Daniel", "Okafor", "Senior Technical Recruiter", "recruiter"),
    ("Mei", "Tan", "Staff Software Engineer", "referrer"),
]
ROLE = "Backend Engineer"
TEMPLATE_NAME = "Demo template"
TEMPLATE_SUBJECT = "[[Interested in|Curious about]] {role} roles at {company_name}"
TEMPLATE_BODY = (
    "<p>Hi {contact_name},</p>"
    "<p>[[I saw|I noticed]] that {company_name} is hiring for {role}, and I'd like to be "
    "considered. The problems your team works on line up closely with what I've been "
    "building for the last few years.</p>"
    "<p>Would you be open to a [[short|quick]] 15-minute call this week, or could you point me "
    "to the right person?</p>"
)


async def seed(user_id: int, addresses: list[str]) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        if await db.get(User, user_id) is None:
            raise SystemExit(f"No user with id {user_id}")

        org_id = hashlib.md5(f"demo-company-{user_id}".encode()).hexdigest()[:24]
        company_id = (
            await db.execute(
                pg_insert(Company)
                .values(apollo_org_id=org_id, name="Demo Co", domain="demo.example")
                .on_conflict_do_update(index_elements=["apollo_org_id"], set_={"name": "Demo Co"})
                .returning(Company.id)
            )
        ).scalar_one()
        user_company_id = (
            await db.execute(
                pg_insert(UserCompany)
                .values(
                    user_id=user_id,
                    company_id=company_id,
                    roles=[ROLE],
                    locations=[],
                    status="ready",
                    contacts_found=len(addresses),
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "company_id"],
                    set_={"status": "ready", "contacts_found": len(addresses)},
                )
                .returning(UserCompany.id)
            )
        ).scalar_one()

        for index, address in enumerate(addresses):
            first, last, title, kind = PEOPLE[index % len(PEOPLE)]
            email = address.strip().lower()
            contact = await db.scalar(
                select(Contact).where(Contact.source == "hunter", Contact.email == email)
            )
            if contact is None:
                contact = Contact(
                    source="hunter",
                    company_id=company_id,
                    first_name=first,
                    last_name=last,
                    title=title,
                    has_email=True,
                    email=email,
                    email_status="valid",
                    email_source="hunter",
                    revealed_at=now,
                )
                db.add(contact)
                await db.flush()
            else:
                contact.email_status = "valid"

            await db.execute(
                pg_insert(UserContact)
                .values(
                    user_id=user_id,
                    contact_id=contact.id,
                    user_company_id=user_company_id,
                    type=kind,
                    relevance=90 - index * 5,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "contact_id"])
            )
            await db.execute(
                update(UserContact)
                .where(UserContact.user_id == user_id, UserContact.contact_id == contact.id)
                .values(
                    stage=OutreachStage.NEW,
                    stage_changed_at=now,
                    ai_stops_outreach=False,
                    follow_up_count=0,
                    first_contacted_at=None,
                    last_contacted_at=None,
                    replied_at=None,
                )
            )
            logger.info("Contact %s %s <%s> (%s)", first, last, email, kind)

        await db.execute(
            update(EmailTemplate)
            .where(EmailTemplate.user_id == user_id, EmailTemplate.is_default.is_(True))
            .values(is_default=False)
        )
        template = await db.scalar(
            select(EmailTemplate).where(
                EmailTemplate.user_id == user_id, EmailTemplate.name == TEMPLATE_NAME
            )
        )
        if template is None:
            db.add(
                EmailTemplate(
                    user_id=user_id,
                    name=TEMPLATE_NAME,
                    subject=TEMPLATE_SUBJECT,
                    body_html=TEMPLATE_BODY,
                    is_default=True,
                )
            )
        else:
            template.subject, template.body_html, template.is_default = (
                TEMPLATE_SUBJECT,
                TEMPLATE_BODY,
                True,
            )
        await db.commit()
    await async_engine.dispose()
    logger.info("Seeded Demo Co with %d contacts and a default template", len(addresses))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument(
        "--to", action="append", required=True, help="An address to email; repeat for more"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(seed(args.user_id, args.to))


if __name__ == "__main__":
    main()
