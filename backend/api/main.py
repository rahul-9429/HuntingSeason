from dotenv import load_dotenv

# override=True: backend/.env wins over machine-wide variables, which other
# projects on the same machine may set under the same names (DATABASE_URL, ...).
load_dotenv(override=True)

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.api_services import company_search
from api.routers import (
    career_profile,
    clerk_webhook,
    companies,
    contacts,
    hunt,
    mailbox,
    outreach,
    preferences,
    profile,
    proposals,
    resumes,
    templates,
    threads,
    user,
    webhooks,
)
from db.session import async_engine
from services import hunter, s3, tavily
from services.hunt import apollo, apollo_cache
from services.email_providers import microsoft_provider
from services.json_logging import configure_logging
from services.redis import close_redis

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    company_search.warn_if_unconfigured()
    s3.warn_if_unconfigured()
    hunter.warn_if_unconfigured()
    tavily.warn_if_unconfigured()
    cache_cleanup = asyncio.create_task(apollo_cache.run_cleanup_forever())
    yield
    cache_cleanup.cancel()
    with suppress(asyncio.CancelledError):
        await cache_cleanup
    await apollo.close_client()
    await hunter.close_client()
    await tavily.close_client()
    await microsoft_provider.close_client()
    await close_redis()
    await async_engine.dispose()


app = FastAPI(title="Hunting Season API", lifespan=lifespan)

WEB_URLS = [
    os.getenv("WEB_URL", "http://localhost:3000"),
]

# Lets the Next.js frontend call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=WEB_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clerk_webhook.router)
app.include_router(user.router)
app.include_router(companies.router)
app.include_router(resumes.router)
app.include_router(career_profile.router)
app.include_router(profile.router)
app.include_router(preferences.router)
app.include_router(outreach.router)
app.include_router(contacts.router)
app.include_router(hunt.router)
app.include_router(mailbox.router)
app.include_router(webhooks.router)
app.include_router(templates.router)
app.include_router(proposals.router)
app.include_router(threads.router)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
