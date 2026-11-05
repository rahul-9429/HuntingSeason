# Importing every model here registers it on Base.metadata, which Alembic reads.
from .apollo_cache import ApolloCache
from .career_profile import CareerProfile
from .company import Company
from .contact import Contact
from .credit_grant import CreditGrant
from .credit_wallet import CreditWallet
from .daily_send_usage import DailySendUsage
from .email_event import EmailEvent
from .email_template import EmailTemplate
from .emailed_address import EmailedAddress
from .hunt_settings import HuntSettings
from .inbox_thread import InboxThread
from .mailbox import Mailbox
from .outreach_settings import OutreachSettings
from .reply_proposal import ReplyProposal
from .resume import Resume
from .sent_email import SentEmail
from .user import User
from .user_company import UserCompany
from .user_contact import UserContact
from .user_profile import UserProfile

__all__ = [
    "ApolloCache",
    "CareerProfile",
    "Company",
    "Contact",
    "CreditGrant",
    "CreditWallet",
    "DailySendUsage",
    "EmailEvent",
    "EmailTemplate",
    "EmailedAddress",
    "HuntSettings",
    "InboxThread",
    "Mailbox",
    "OutreachSettings",
    "ReplyProposal",
    "Resume",
    "SentEmail",
    "User",
    "UserCompany",
    "UserContact",
    "UserProfile",
]
