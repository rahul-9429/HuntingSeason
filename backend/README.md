# Backend

FastAPI app. Clerk handles login, so we never see a password: every request
carries a Clerk-signed token, and we map it to a row in our `users` table.

## Run it

You need Python 3.12+, Postgres and Redis. From `backend/`:

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env          # then fill it in, see below
alembic upgrade head
uvicorn api.main:app --reload --port 8000
python -m tasks.worker        # in a second terminal: background tasks
```

`GET /user/me` with a valid token returns your user id and email (and creates
your row the first time). Without a token you get a 401.

## Login

The frontend signs the user in with Clerk, then sends a token from the
`fastapi-backend` JWT template on every call (`frontend/lib/api/client.ts`).
We check the token against Clerk's signing keys, read the Clerk user id and
email, and find the user (cached in memory for 5 minutes). On first login we
create the row, or link an existing row with the same email. The
`user.created` webhook does the same thing with the user's real name; login
works without it.

The code is in `api/dependencies/authenticate.py` and `api/api_services/users.py`,
with the webhook in `api/routers/clerk_webhook.py`.

## Clerk setup

- A JWT template named exactly `fastapi-backend` with the claims
  `{ "email": "{{user.primary_email_address}}" }`.
- A webhook to `<backend URL>/clerk_webhook` for `user.created`, with its
  signing secret in `CLERK_WEBHOOK_SECRET`. Locally, use a tunnel like ngrok.
- Keep email verification on. Linking accounts by email depends on it.
- The Frontend API URL (API keys page) goes in `CLERK_FRONTEND_API`.

## Environment

| Variable | What it's for |
|---|---|
| `DATABASE_URL` | `postgresql://…` |
| `CLERK_FRONTEND_API` | Token issuer and where the signing keys come from |
| `CLERK_WEBHOOK_SECRET` | Verifies webhook signatures |
| `WEB_URL` | Frontend origin, for CORS |
| `APOLLO_API_KEY` | Must be a master key (company search and People Search) |
| `OPENAI_API_KEY` | The LLM calls |
| `HUNTER_API_KEY`, `TAVILY_API_KEY` | Optional contact search fallbacks |
| `OPENAI_FILTER_MODEL` | Defaults to `gpt-5.6-luna` |
| `OPENAI_RESUME_MODEL` | Model that reads a résumé PDF, defaults to `OPENAI_FILTER_MODEL` |
| `OPENAI_PRICE_INPUT_PER_MTOK`, `OPENAI_PRICE_OUTPUT_PER_MTOK` | Optional, to log what each LLM call cost |
| `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Private S3 bucket for résumé PDFs, and credentials that can put/get `resumes/*` in it |
| `SIGNUP_CREDITS` | One-time credits granted on sign-up, default 50 |
| `AUTO_HUNT_EVERY_HOURS` | How long after its last run Auto-Hunt may run again, default 24 |
| `JOB_POSTED_WITHIN_DAYS` | Default "posted within" window for company searches and Auto-Hunt, default 30 |
| `COMPANY_SEARCHES_PER_MINUTE` | Default 10 |
| `OUTREACH_ADDS_PER_MINUTE` | Default 20 |
| `RESUME_UPLOADS_PER_DAY` | Default 10 |
| `REDIS_URL` | Task queue, locks and OAuth state. Default `redis://localhost:6379/0` |
| `ENCRYPTION_KEY` | Fernet key for the mailbox tokens we store |
| `GMAIL_CLIENT_SECRETS_B64` | base64 of the Google "web" OAuth client JSON |
| `MSFT_CLIENT_SECRETS_B64` | base64 of `{"client_id", "client_secret"}` for the Microsoft app |
| `DAILY_SEND_CAP` | Most emails a mailbox sends a day, default 20 |
| `WORKER_ID` | Unique per worker process, default `worker-1` |
| `BACKEND_HOST` | Public https URL of this API, for Outlook notifications |
| `GMAIL_PUBSUB_TOPIC` | Pub/Sub topic for Gmail push notifications, `projects/<project>/topics/<topic>`, see Replies |
| `OPENAI_MODEL` | Outreach emails, reply drafts and classification. Defaults to `gpt-5.6-luna` |

`backend/.env` wins over variables already set on the machine, so another
project's `DATABASE_URL` can't sneak in.

## Company search

You describe the companies you want ("SaaS startups in the UAE hiring for
sales roles") and an LLM turns that into Apollo filters. We fetch 100 hiring
companies per page, up to 10 pages. "Load more" reuses the same filters, so it
doesn't call the LLM again. Each card links to the company's LinkedIn jobs
page for free, or can list its postings in the app for a credit.

A new search or a new page costs 1 credit, and anything someone already
fetched is free: search pages are cached for 24 hours, postings for 7 days.
Each user is granted 50 credits on sign-up (`SIGNUP_CREDITS`), held in a wallet
(`credit_wallets`) that nothing resets, so unused credits roll over for good.
Searches are still capped at 10 a minute, and a failed Apollo call refunds its
credit.

Every grant is also written to `credit_grants`, whose `reason` is unique per
user, so `credits.grant(db, user_id, amount, reason)` is idempotent and adds to
the balance instead of replacing it. That is the seam for recurring top-ups: a
monthly job calls `credits.grant(db, user_id, MONTHLY_CREDITS,
credits.monthly_grant())`, which grants once per calendar month and leaves
whatever the user hadn't spent in place. Nothing schedules that yet.

The code is in `api/api_services/company_search.py`, with Apollo in `apollo.py`
and the LLM prompt in `company_filters.py`.

## Contacts

"Add to contacts" on a company finds up to two people there who could help
you get in, usually a hiring manager and a recruiter. It runs in the
background and tries three sources in order, each filling only what's still
missing:

1. **Apollo**. We search the company by its Apollo id for the titles we want,
   in your search's location first. The search is free but only gives a first
   name and a masked last name, so we reveal the people we pick right away.
2. **Hunter** (1 credit). Searches the company's domain and keeps people with
   a valid email.
3. **Tavily** (1 credit). A LinkedIn web search, with an LLM pulling names out
   of the results. We only keep people whose profile Tavily actually returned,
   and they only get an email if Hunter can verify it.

Hunter and Tavily are skipped without their keys, refund the credit if they
find nobody, and cache their results for 30 days. Each person gets a score out
of 100, based mostly on how closely their title matches what we were looking
for, plus a bit for having an email or being in your location.

Revealing an Apollo contact costs a credit and gets their full name, LinkedIn
and verified email. It's saved on the shared contact, so it's free for anyone
after that. If you're out of credits when you add a company, its Apollo
contacts stay masked and you can reveal them later from /contacts.

Companies and people are stored once (`companies`, `contacts`) and linked to
each user (`user_companies`, `user_contacts`). Each contact remembers where it
came from. Adding a company again doesn't search again unless the last search
failed, or found nobody over a month ago.

Most of this is in `api/api_services/contact_finder.py`, with reveal in
`contacts.py`. Hunter, Tavily and the LLM calls are in `services/hunter.py`,
`services/tavily.py` and `services/contact_llm.py`.

## Mailbox

Each user connects one Gmail or Outlook mailbox to send from:

1. `GET /mailbox/{gmail|microsoft}/auth-url?redirect_uri=…` returns the
   provider's consent page. `redirect_uri` must be a page under `WEB_URL`, and
   registered with the provider. The frontend uses `<WEB_URL>/connect/gmail`
   and `<WEB_URL>/connect/microsoft`.
2. The provider sends the user back to that page with a `code` and `state`, and
   the frontend posts the full URL to `POST /mailbox/connect`. A `state` works
   once, within 10 minutes, and only for the user who asked for it.

We store the tokens Fernet-encrypted in `mailboxes.credentials` and refresh
them when they expire. If the provider says the grant was revoked, the mailbox
becomes `needs_reconnect` until the user connects it again. An address can
only be connected by one user.

`POST /mailbox/test-send` sends an email, or with `reply_to_sent_email_id` a
reply in that thread, and records it in `sent_emails`.

Provider setup:

- **Google**: a "web" OAuth client with your redirect URIs, and the Gmail API
  enabled. Gmail's read and send scopes are restricted, so until Google
  verifies the app only its test users can connect.
- **Microsoft**: an Entra app for "any organizational directory and personal
  Microsoft accounts", with a Web redirect URI, a client secret and the
  delegated Graph permissions `Mail.ReadWrite`, `Mail.Send` and `User.Read`.

The code is in `api/api_services/mailbox.py`, `services/mailbox_manager.py` and
`services/email_providers/`.

## Replies

Every message in a thread we started is saved in `email_events`, whichever
side wrote it; other mail is ignored. Gmail tells us about new mail through
Pub/Sub, and Outlook through Graph subscriptions on the Inbox and Sent Items,
both set up when the mailbox connects and renewed every 6 hours. A worker
reads each batch about 20 seconds later. Every 15 minutes we also check each
mailbox directly, in case a notification went missing.

A reply makes the contact `hot` and stops their follow-ups. Out-of-office
replies and bounces don't count (we go by `Auto-Submitted` and similar
headers). An AI reads every reply and labels it; replies it couldn't read, say
while OpenAI was down, are retried every 10 minutes for 3 days:

| Label | What happens |
|---|---|
| `inquiry` (interest, a question, a CV request) | Drafts an answer |
| `referral` (talk to someone else) | Drafts an answer and stops outreach; never auto-sent |
| `not_interested` | Contact becomes `dead` |
| `disqualified` (remove me) | Contact becomes `dead`; they're never emailed again |
| `bounced` | If it names the contact's address, a hard bounce marks it invalid for everyone and the contact `dead` |
| `neutral` (out of office, thanks) | Nothing more |

Drafts are at `/proposals`, where you can edit, approve (sends it in the
thread) or reject them. The inbox shows a thread's pending draft as `draft`
in `GET /v1/threads/{id}`. With `auto_send_replies` on, an inquiry draft sends
itself after 24 hours; turning that off cancels drafts already scheduled. A
new message in the thread replaces its pending draft, and a draft can't be
sent once the thread has moved on.

Gmail setup in Google Cloud: create a Pub/Sub topic, give
`gmail-api-push@system.gserviceaccount.com` the Publisher role on it, and add a
push subscription to `<BACKEND_HOST>/webhooks/gmail`. Put the topic in
`GMAIL_PUBSUB_TOPIC`:

```bash
GMAIL_PUBSUB_TOPIC=projects/<project>/topics/<topic>
```

`/webhooks/gmail` accepts any push, so treat the URL as the only thing standing
between the internet and a forced mailbox sync. Without `GMAIL_PUBSUB_TOPIC`,
Gmail replies are still found by the 15-minute safety sync.

## Automated outreach

Once enabled (`PUT /v1/outreach/settings`), the worker emails your contacts
every hour (`POST /v1/outreach/run` does it now). Only people get emailed,
never a company address, and only contacts with an email address. Each
contact's `stage` in `user_contacts` moves like this:

- `new` → `contacted` after the first email. Follow-ups go in the same thread
  every `follow_up_interval_days`, up to `max_follow_ups`.
- `hot` once they reply.
- `dead` if the follow-ups run out without a reply, or the reply was a no.
  Writing to them yourself from your mail client puts a no-reply contact back
  to `contacted`, and the next follow-up waits a full interval after your email.

Nobody gets a first email twice: every address emailed is kept in
`emailed_addresses`, so removing a company and adding it again doesn't restart
outreach to its people. Turning outreach off stops a run that's in progress.

There are two writers, and `email_agent` is the default. `email_agent` writes the whole
email from your profile, so it needs no template. `template` personalises your
default template (`/templates`; `[[a|b]]` picks one at random, and
`{contact_name}`, `{company_name}` and `{role}` are filled in). If the AI is
down, a template is sent as written, but nothing else is sent: no generic
emails. Preview either one with `POST /v1/outreach/preview` (`writer` and
`template_id` are optional; the answer says which template it used).

Parsing a résumé also writes a starter email template from your profile, marked
`is_generated` and set as the default. Re-uploading a résumé rewrites it, so
the template keeps up with your profile. Editing a template clears
`is_generated`, and from then on it is yours and never overwritten. Creating
your first template makes it the default, and deleting the default promotes
another, so the template writer is never left with nothing. `GET
/v1/outreach/settings` carries `has_default_template`, `has_profile` and a
`blocker` sentence that is set when the chosen writer cannot produce anything,
which is what the UI shows instead of claiming outreach is running.

`POST /v1/contacts/{id}/outreach` sends a first email you wrote yourself
(`subject`, `html`, and the `writer` and `templateId` of the preview it came
from). It follows the same rules as the automated first email: never to
someone already emailed, within the daily limit, and the contact becomes
`contacted` with follow-ups to come. `POST /v1/outreach/run` runs outreach
now instead of waiting for the hour.

A mailbox sends at most 20 emails a day (`DAILY_SEND_CAP`), counting first
emails, follow-ups and approved replies. A new mailbox warms up first: 15 a
day for its first 3 days, then the full 20. A fifth of each day is kept for
follow-ups. `GET /mailbox` shows the share of the last 7 days' emails that
bounced.

What the AI knows about you comes from your Profile tabs and career profile:
name, headline, pitch, bio, current company and title, years of experience,
seniority, field, top skills, industries, location, where you're open to
working, the company sizes you've worked at, up to 3 highlights from your
latest role, and your LinkedIn and portfolio (`get_user_info` in
`services/outreach/user_info.py`). Every email, follow-up and reply draft is
written from it, and it's told never to claim more than it says. `email_agent`
needs at least a current title, skills, a pitch or a headline, so it skips
users without any.
The prompts are in `services/email_event/prompts.py`.

To try it: `python scripts/seed_demo_leads.py --user-id 1 --to you+a@example.com --to you+b@example.com`
creates a demo company with those contacts and a default template.

## Inbox

`/v1/threads` lists every thread we started with a contact from the connected
mailbox, newest first, built from `email_events`. A thread's id is the id of
its first message, and any message id in it opens it too.

- `GET /v1/threads?filter=all|hiring_manager|recruiter|referrer&q=…`: `q`
  matches the contact's name, company or subject. Counts and `unread` ignore
  the filter and search.
- `GET /v1/threads/{id}`: every message, oldest first, with quoted history
  cut off.
- `PATCH /v1/threads/{id}` with `unread`, `archived` or `notes`. A thread is
  unread when they wrote last and you haven't opened it since. An archived
  thread comes back when they write again.
- `POST /v1/threads/{id}/messages` replies in the thread from the mailbox, to
  the address they last wrote from (or the one we emailed). It counts toward
  the daily limit, adds your signature if you've set one, and counts as you
  writing to them, so the next follow-up waits.

Read, archive and notes live in `inbox_threads`. The code is in
`api/api_services/threads.py`.

## Background tasks

`python -m tasks.worker` is a separate process from the API. It runs tasks
from the Redis list `{env}:tasks:queue` (`dev` or `prod`), which anything can
add to with `services.redis.push_task(name, payload)`, and a scheduler for
periodic jobs (`tasks/scheduler.py`). Handlers live in `tasks/handlers/` and
are listed in `tasks/registry.py`.

A worker keeps each task on its own processing list while it runs, and puts
back whatever is left there when it starts, so a killed worker loses nothing.
That's why each worker needs its own `WORKER_ID`. Failed tasks aren't retried,
so handlers must be safe to run twice. To see it work:

```bash
redis-cli LPUSH dev:tasks:queue '{"task": "ping", "payload": {"sleep": 30}}'
```

Kill the worker within those 30 seconds and start it again: the ping runs again.

## Logs

Every log line is one JSON object on stdout, which Railway parses. Pass ids
as `extra` so you can filter on them (`@user_id:5`, `@level:error`):

```python
logger.info("Contact search for %s: %s", org_id, status, extra={"org_id": org_id, "user_id": user_id})
```

Run uvicorn as a single process to get JSON for every line. With `--reload`
or `--workers`, a few startup lines come out as plain text.

## Résumé onboarding

Optional. After sign-up the frontend offers `/onboarding`, where the user can
upload a PDF résumé (or skip; it's also under Profile → Résumé later).

1. `POST /v1/resumes` with the PDF as multipart field `file`. Only PDFs
   (checked by extension and the `%PDF-` header) of 5 MB or less. The API
   stores it in S3 at `resumes/{user_id}/{uuid}.pdf` (SSE-S3) and answers
   `202` with `status: "parsing"`.
2. A background task sends the PDF to OpenAI as a file (`store=False`) with a
   strict schema, and the result becomes the user's **career profile**
   (`career_profiles`).
3. The client polls `GET /v1/resumes/{id}` (or `/latest`, `null` before the
   first upload) until `parsed` or `failed`. A row still `parsing` after 5 min (lost task) reads as `failed`.
4. `GET` / `PUT /v1/career-profile` reads or edits the profile:
   `current_title`, `seniority`, `function`, `top_skills`, `industries`,
   `location`, `open_to_locations`, `company_size_history`.

The same parse also reads what the Profile tabs show (`user_profiles`), in a
second LLM call. If that call fails, the parse still succeeds.

- `GET` / `PATCH /v1/profile` (General): a new résumé only fills empty fields,
  so your edits stay. Name and email default to the account's.
- `GET /v1/profile/experience`: roles and education, replaced by each new
  résumé.
- `GET` / `PATCH /v1/preferences`: target roles, seniority, locations and
  remote, set from the first résumé only if you've never saved preferences.
  Salary and culture are yours to fill.

PATCH changes only the fields sent. These endpoints use camelCase, like the
frontend's types.

**In company search** (`use_profile`, default on), the profile goes to the
filter LLM as background that only fills what the typed query leaves open:
titles at the user's seniority, hiring locations from `open_to_locations` (else `location`'s country),
`company_size_history` → employee ranges, `industries` → keyword tags. The
query always wins. With a profile, an empty query searches from the résumé
alone. The query → filters cache is keyed by the profile too, so an edit
takes effect on the next search. `used_profile` in the response says whether
it applied.

**Bucket setup.** A private bucket (block all public access). The browser
never talks to S3, so no CORS rule is needed. The IAM user needs
`s3:PutObject` and `s3:GetObject` on `arn:aws:s3:::<bucket>/resumes/*`.

| What | File |
|---|---|
| Routes | `api/routers/resumes.py`, `api/routers/career_profile.py` |
| Upload, status | `api/api_services/resumes.py`, `models/resume.py` |
| Background parse | `services/resume_parsing.py` |
| PDF → profile LLM call | `services/resume_extraction.py` |
| S3 (aioboto3) | `services/s3.py` |
| Profile storage | `services/career_profiles.py`, `models/career_profile.py` |
| Profile tabs | `api/routers/profile.py`, `api/routers/preferences.py`, `services/user_profiles.py`, `models/user_profile.py` |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Apollo, Hunter, Tavily, OpenAI, S3 and the database are all stubbed, so an
unexpected outside call fails the test instead of spending a credit.

## Gotchas

- The JWT template name has to match exactly. A 401 saying the email isn't in
  the token means the template wasn't used.
- Each worker caches Clerk id → user id for 5 minutes. If you delete a user or
  move a Clerk id, call `evict_user_cache(clerk_user_id)`.
- There's no password or logout endpoint. Clerk owns all of that.
