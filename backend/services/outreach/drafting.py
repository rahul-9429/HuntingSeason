import html
import logging
import random
import re
from dataclasses import dataclass
from typing import Optional, Sequence

import nh3

from models.email_template import EmailTemplate
from models.enums import Writer
from models.mailbox import Mailbox
from models.outreach_settings import OutreachSettings
from models.sent_email import SentEmail
from services.email_event import openai_client, prompts
from services.email_event.openai_client import LLMError
from services.email_event.prompts import fill
from services.email_providers.utils import (
    html_to_text,
    sanitize_email_html,
    sanitize_signature_html,
)
from services.outreach.eligibility import Lead
from services.outreach.names import extract_first_name
from services.outreach.user_info import UserInfo
from services.schemas.outreach import WrittenEmail

logger = logging.getLogger(__name__)

FOLLOW_UP_MAX_OUTPUT_TOKENS = 1500

_SPINTAX = re.compile(r"\[\[([^\[\]]*)\]\]")
_GREETING = re.compile(r"^\s*([A-Za-z]+)\s+\{contact_name\}")
_LINK_TAG = re.compile(r"<a\b[^>]*>.*?</a\s*>", re.IGNORECASE | re.DOTALL)
_CODE_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_TAG = re.compile(r"<[^>]+>")
_PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_REPLY_PREFIX = re.compile(r"^\s*re:", re.IGNORECASE)
_LEFTOVER = re.compile(r"__LINK_\d+__|\{(?:name|contact_name|company_name|role)\}")
_SIGN_OFF = re.compile(
    r"(?:^|\n)[ \t]*(?:best regards|kind regards|best|regards|thanks|thank you|sincerely|cheers)"
    r"[ \t]*,?[ \t]*(?:\n[ \t]*[^\n]{1,60})?\s*$",
    re.IGNORECASE,
)


class DraftingError(Exception):
    pass


@dataclass(frozen=True)
class DraftContext:
    settings: OutreachSettings
    mailbox: Mailbox
    user_info: UserInfo
    template: Optional[EmailTemplate]


@dataclass(frozen=True)
class Draft:
    subject: str
    html: str
    writer: Writer
    template_id: Optional[int]
    from_name: Optional[str]


def resolve_spintax(text: str) -> str:
    return _SPINTAX.sub(lambda group: random.choice(group.group(1).split("|")), text)


def fill_placeholders(text: str, lead: Lead, first_name: str) -> str:
    return (
        text.replace("{contact_name}", first_name)
        .replace("{company_name}", lead.company.name or "your team")
        .replace("{role}", lead.roles[0] if lead.roles else "a role on your team")
    )


def greeting_word(template_body: str) -> str:
    match = _GREETING.match(html.unescape(_TAG.sub("", template_body)))
    return match.group(1) if match else "Hi"


def _protect_links(body: str) -> tuple[str, list[str]]:
    links: list[str] = []

    def placeholder(match: re.Match[str]) -> str:
        links.append(match.group(0))
        return f"__LINK_{len(links) - 1}__"

    return _LINK_TAG.sub(placeholder, body), links


def _restore_links(body: str, links: list[str]) -> str:
    for index, link in enumerate(links):
        body = body.replace(f"__LINK_{index}__", link)
    return body


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE.sub("", text.strip()).strip()


def style_guard(text: str, *, user_id: int, field: str) -> str:
    text = text.replace(" — ", ", ").replace("—", ", ")
    found = [
        word
        for word in prompts.BANNED_BUZZWORDS
        if re.search(rf"\b{re.escape(word)}", text, re.IGNORECASE)
    ]
    if found:
        logger.warning(
            "Generated %s uses banned words: %s",
            field,
            ", ".join(found),
            extra={"user_id": user_id, "banned_words": found},
        )
    return text


def strip_sign_off(body: str) -> str:
    return _SIGN_OFF.sub("", body.rstrip()).rstrip()


def paragraphs_html(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    return sanitize_email_html(
        "".join(
            "<p>" + "<br>".join(html.escape(line.strip()) for line in part.splitlines()) + "</p>"
            for part in paragraphs
        )
    )


def default_signature(mailbox: Mailbox, user_info: UserInfo) -> str:
    first = extract_first_name(mailbox.from_name, mailbox.email)
    if first == "there":
        first = extract_first_name(user_info.name, mailbox.email)
    if first == "there":
        return "<p>Best regards</p>"
    return f"<p>Best,<br>{html.escape(first)}</p>"


def template_signature(ctx: DraftContext, template: Optional[EmailTemplate]) -> str:
    return (
        (template.signature_html if template else None)
        or ctx.settings.signature_html
        or default_signature(ctx.mailbox, ctx.user_info)
    )


def agent_signature(ctx: DraftContext) -> str:
    if ctx.settings.signature_html:
        plain = nh3.clean(
            ctx.settings.signature_html,
            tags={"p", "br", "div", "span", "strong", "b", "em", "i"},
            attributes={},
            link_rel=None,
        )
        plain = _PHONE.sub("", plain)
        if html_to_text(plain).strip():
            return plain
    return default_signature(ctx.mailbox, ctx.user_info)


def with_signature(body_html: str, signature_html: str) -> str:
    signature = sanitize_signature_html(signature_html)
    if not signature:
        return body_html
    return f'{body_html}<div style="margin-top:20px;">{signature}</div>'


def sender_name(ctx: DraftContext, template: Optional[EmailTemplate]) -> Optional[str]:
    return (
        (template.sender_name if template else None)
        or ctx.settings.sender_name
        or ctx.mailbox.from_name
        or None
    )


def _instructions(settings: OutreachSettings) -> str:
    if not settings.writer_instructions:
        return ""
    return fill(prompts.EMAIL_AGENT_INSTRUCTIONS_BLOCK, writer_instructions=settings.writer_instructions)


def _roles(lead: Lead) -> str:
    return ", ".join(lead.roles) or "(not stated)"


async def first_touch(ctx: DraftContext, lead: Lead, writer: Optional[Writer] = None) -> Draft:
    if (writer or ctx.settings.writer) == Writer.TEMPLATE:
        return await _from_template(ctx, lead)
    return await _email_agent(ctx, lead)


async def _from_template(ctx: DraftContext, lead: Lead) -> Draft:
    template = ctx.template
    if template is None:
        raise DraftingError("The template writer needs a default template")
    first_name = lead.first_name
    subject = fill_placeholders(resolve_spintax(template.subject), lead, first_name).strip()
    body = fill_placeholders(resolve_spintax(template.body_html), lead, first_name)
    if not template.skip_ai:
        body = await _personalize(ctx, lead, body, greeting_word(template.body_html), first_name)
    body = sanitize_email_html(body)
    if not subject or not html_to_text(body):
        raise DraftingError("The template produced an empty subject or body")
    return Draft(
        subject=subject,
        html=with_signature(body, template_signature(ctx, template)),
        writer=Writer.TEMPLATE,
        template_id=template.id,
        from_name=sender_name(ctx, template),
    )


async def _personalize(
    ctx: DraftContext, lead: Lead, body: str, greeting: str, first_name: str
) -> str:
    protected, links = _protect_links(body)
    if first_name == "there":
        name_instruction = fill(prompts.NAME_INSTRUCTION_THERE, greeting=greeting)
    else:
        name_instruction = fill(
            prompts.NAME_INSTRUCTION_NAMED,
            greeting=greeting,
            first_name=first_name,
            raw_name=lead.full_name,
        )
    user_id = lead.user_contact.user_id
    try:
        text = await openai_client.generate_text(
            system=fill(prompts.TEMPLATE_PERSONALIZER_SYSTEM, greeting=greeting),
            user=fill(
                prompts.TEMPLATE_PERSONALIZER_USER,
                first_name=first_name,
                title=lead.contact.title or "Unknown",
                recipient_type=lead.recipient_type,
                company=lead.company.name,
                roles=_roles(lead),
                user_info=ctx.user_info.as_prompt(),
                body=protected,
                name_instruction=name_instruction,
            ),
            user_id=user_id,
            purpose="Template personalizer",
        )
    except LLMError:
        logger.warning(
            "Sending the template unpersonalized to contact %s",
            lead.user_contact.id,
            extra={"user_id": user_id, "user_contact_id": lead.user_contact.id},
        )
        return body
    personalized = _restore_links(_strip_code_fences(text), links)
    if _LEFTOVER.search(personalized) or any(link not in personalized for link in links):
        logger.warning(
            "Personalized email lost a link or kept a placeholder; sending the template as written",
            extra={"user_id": user_id, "user_contact_id": lead.user_contact.id},
        )
        return body
    return style_guard(personalized, user_id=user_id, field="body")


async def _email_agent(ctx: DraftContext, lead: Lead) -> Draft:
    if not ctx.user_info.has_profile:
        raise DraftingError("The email agent needs the job seeker's profile to write from")
    first_name = lead.first_name
    greeting_rule = (
        fill(prompts.EMAIL_AGENT_GREETING_NAMED, first_name=first_name)
        if first_name != "there"
        else prompts.EMAIL_AGENT_GREETING_THERE
    )
    user_id = lead.user_contact.user_id
    try:
        written = await openai_client.generate_structured(
            system=fill(
                prompts.EMAIL_AGENT_SYSTEM,
                user_info=ctx.user_info.as_prompt(),
                instructions_block=_instructions(ctx.settings),
                greeting_rule=greeting_rule,
            ),
            user=fill(
                prompts.EMAIL_AGENT_USER,
                first_name=first_name,
                title=lead.contact.title or "Unknown",
                recipient_type=lead.recipient_type,
                company=lead.company.name,
                domain=lead.company.domain or "Unknown",
                roles=_roles(lead),
                locations=", ".join(lead.locations) or "(not stated)",
            ),
            schema=WrittenEmail,
            user_id=user_id,
            purpose="Email agent writer",
        )
    except LLMError as exc:
        raise DraftingError("The email agent couldn't write the email") from exc

    subject = style_guard(written.subject.strip(), user_id=user_id, field="subject")
    body = sanitize_email_html(style_guard(written.body, user_id=user_id, field="body"))
    if not subject or not html_to_text(body):
        raise DraftingError("The email agent returned an empty subject or body")
    return Draft(
        subject=subject,
        html=with_signature(body, agent_signature(ctx)),
        writer=Writer.EMAIL_AGENT,
        template_id=None,
        from_name=sender_name(ctx, None),
    )


def reply_subject(subject: str) -> str:
    return subject if _REPLY_PREFIX.match(subject) else f"Re: {subject}"


async def follow_up(
    ctx: DraftContext,
    lead: Lead,
    first_email: SentEmail,
    earlier_follow_ups: Sequence[SentEmail],
    attempt: int,
    template: Optional[EmailTemplate],
) -> Draft:
    final = attempt >= ctx.settings.max_follow_ups
    user_id = lead.user_contact.user_id
    try:
        text = await openai_client.generate_text(
            system=fill(
                prompts.FOLLOW_UP_SYSTEM,
                first_name=lead.first_name,
                final_rule=prompts.FOLLOW_UP_FINAL_RULE if final else prompts.FOLLOW_UP_RULE,
                instructions_block=_instructions(ctx.settings),
            ),
            user=fill(
                prompts.FOLLOW_UP_USER,
                attempt=str(attempt),
                max_follow_ups=str(ctx.settings.max_follow_ups),
                first_name=lead.first_name,
                title=lead.contact.title or "Unknown",
                recipient_type=lead.recipient_type,
                company=lead.company.name,
                roles=_roles(lead),
                user_info=ctx.user_info.as_prompt(),
                first_email=html_to_text(first_email.body_html),
                earlier_follow_ups="\n\n---\n\n".join(
                    html_to_text(email.body_html) for email in earlier_follow_ups
                )
                or "(none)",
            ),
            user_id=user_id,
            purpose="Follow-up",
            max_output_tokens=FOLLOW_UP_MAX_OUTPUT_TOKENS,
        )
    except LLMError as exc:
        raise DraftingError("Couldn't write the follow-up") from exc

    body = paragraphs_html(
        strip_sign_off(style_guard(_strip_code_fences(text), user_id=user_id, field="body"))
    )
    if not html_to_text(body):
        raise DraftingError("The follow-up came back empty")
    writer = first_email.writer or Writer.TEMPLATE
    signature = agent_signature(ctx) if writer == Writer.EMAIL_AGENT else template_signature(ctx, template)
    return Draft(
        subject=reply_subject(first_email.subject),
        html=with_signature(body, signature),
        writer=writer,
        template_id=first_email.template_id,
        from_name=sender_name(ctx, template if writer == Writer.TEMPLATE else None),
    )
