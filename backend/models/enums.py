from enum import StrEnum

import sqlalchemy as sa


class MailboxProvider(StrEnum):
    GMAIL = "gmail"
    MICROSOFT = "microsoft"


class MailboxStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"


class OutreachStage(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    HOT = "hot"
    DEAD = "dead"


class Writer(StrEnum):
    TEMPLATE = "template"
    EMAIL_AGENT = "email_agent"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class DeliveryStatus(StrEnum):
    SENT = "sent"
    BOUNCED_SOFT = "bounced_soft"
    BOUNCED_HARD = "bounced_hard"


class ReplyLabel(StrEnum):
    NOT_INTERESTED = "not_interested"
    REFERRAL = "referral"
    DISQUALIFIED = "disqualified"
    INQUIRY = "inquiry"
    NEUTRAL = "neutral"
    BOUNCED = "bounced"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


def db_enum(enum_cls: type[StrEnum]) -> sa.Enum:
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )
