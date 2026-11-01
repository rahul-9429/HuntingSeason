export type Hue = "slate" | "blue" | "indigo" | "teal" | "gray" | "sky";

export type ContactType = "hiring_manager" | "recruiter" | "referrer";
export type Channel = "email";

export type OutreachStage = "new" | "contacted" | "hot" | "dead";
export type ContactSource = "apollo" | "hunter" | "tavily";

export interface Company {
  id: string;
  name: string;
  domain: string | null;
  logoUrl: string | null;
  linkedinUrl: string | null;
}

export interface Signal {
  kind: "hiring" | "background" | "stack" | "activity" | "network";
  label: string;
}

export interface Contact {
  id: string;
  name: string;
  title: string;
  type: ContactType;
  companyId: string;
  location: string | null;
  email: string | null;
  emailMasked: string | null;
  linkedin: string | null;
  photoUrl: string | null;
  relevance: number;
  signals: Signal[];
  foundAt: string;
  stage: OutreachStage;
  revealed: boolean;
  source: ContactSource;
  emailSource: ContactSource | null;
  hook?: string;
}

export interface ContactWithCompany extends Contact {
  company: Company;
}

export interface Message {
  id: string;
  from: "me" | "them";
  body: string;
  sentAt: string;
}

export type ReplyLabel = "inquiry" | "referral" | "not_interested" | "disqualified" | "neutral" | "bounced";

export interface ReplyDraft {
  id: string;
  label: ReplyLabel;
  reason: string;
  subject: string;
  body: string;
  autoSendAt: string | null;
}

export interface Thread {
  id: string;
  contactId: string;
  channel: Channel;
  subject: string;
  unread: boolean;
  archived?: boolean;
  updatedAt: string;
  notes: string;
  messages: Message[];
  draft: ReplyDraft | null;
}

export interface ThreadWithContact extends Thread {
  contact: ContactWithCompany;
}

export type InboxFilter = "all" | "drafts" | ContactType;

export interface ThreadSummary {
  id: string;
  contact: ContactWithCompany;
  channel: Channel;
  subject: string;
  unread: boolean;
  hasDraft: boolean;
  updatedAt: string;
  lastMessage: Pick<Message, "from" | "body">;
}

export interface ThreadList {
  items: ThreadSummary[];
  counts: Record<InboxFilter, number>;
  unread: number;
}

export type ThreadPatch = Partial<Pick<Thread, "archived" | "unread" | "notes">>;

export type ContactFilter = "all" | ContactType;

export interface ContactList {
  items: ContactWithCompany[];
  counts: Record<ContactFilter, number>;
  nextCursor: string | null;
}

export interface Credits {
  used: number;
  total: number;
}

export type Seniority = "entry" | "senior" | "manager" | "head" | "director" | "vp" | "c_suite";

export type JobFunction =
  | "engineering"
  | "product"
  | "design"
  | "data"
  | "sales"
  | "marketing"
  | "customer_success"
  | "finance"
  | "operations"
  | "hr"
  | "legal"
  | "other";

export type CompanySize = "1,10" | "11,50" | "51,200" | "201,500" | "501,1000" | "1001,5000" | "5001,10000";

/** What we know about the job seeker, read from their résumé and editable (GET/PUT /v1/career-profile). */
export interface CareerProfile {
  current_title: string | null;
  seniority: Seniority | null;
  function: JobFunction | null;
  top_skills: string[];
  industries: string[];
  location: string | null;
  open_to_locations: string[];
  company_size_history: CompanySize[];
}

export interface Resume {
  id: number;
  file_name: string;
  status: "parsing" | "parsed" | "failed";
  error: string | null;
  created_at: string;
  parsed_at: string | null;
  profile: CareerProfile | null;
}

export interface Experience {
  id: string;
  role: string;
  company: string;
  hue: Hue;
  start: string;
  end: string;
  location: string;
  highlights: string[];
  skills: string[];
}

export type MailProvider = "gmail" | "microsoft";
export type IntegrationId = MailProvider | "google_calendar";

export interface Mailbox {
  provider: MailProvider;
  email: string;
  from_name: string | null;
  status: "active" | "needs_reconnect";
  warmup_day: number;
  daily_cap: number;
  sends_today: number;
  bounce_rate_7d: number | null;
}

export type Writer = "template" | "email_agent";

export interface EmailTemplate {
  id: number;
  name: string;
  subject: string;
  body_html: string;
  signature_html: string | null;
  sender_name: string | null;
  skip_ai: boolean;
  is_default: boolean;
  is_generated: boolean;
  created_at: string;
}

export interface OutreachPreview {
  subject: string;
  html: string;
  writer: Writer;
  template_id: number | null;
}

export interface OutreachSettings {
  enabled: boolean;
  writer: Writer;
  writer_instructions: string | null;
  max_follow_ups: number;
  follow_up_interval_days: number;
  sender_name: string | null;
  signature_html: string | null;
  auto_send_replies: boolean;
  reply_booking_link: string | null;
  reply_facts: string | null;
  reply_cc: string[];
  reply_bcc: string[];
  min_gap_seconds: number;
  max_gap_seconds: number;
  updated_at: string;
  has_default_template: boolean;
  has_profile: boolean;
  blocker: string | null;
}

export interface SendScheduleRow {
  country: string;
  days: number[];
  start_hour: number;
  end_hour: number;
  timezone: string | null;
}

export interface EmailSendSchedule {
  enabled: boolean;
  rows: SendScheduleRow[];
}

export interface HuntSettings {
  enabled: boolean;
  last_run_at: string | null;
  companies_added: number;
  contacts_found: number;
  blocker: string | null;
  credits_left: number;
  run_credit_budget: number;
  run_credit_limit: number;
}

export interface TargetLocation {
  country: string;
  city?: string;
}

export type RemotePreference = "none" | "country" | "apac" | "global";

export interface Education {
  degree: string;
  school: string;
  years: string;
}

export interface ExperienceTimeline {
  items: Experience[];
  education: Education | null;
}

export interface Preferences {
  roles: string[];
  seniority: string[];
  locations: TargetLocation[];
  remote: RemotePreference;
  salary: { current: number; expectedMin: number; expectedTarget: number };
  culture: { workModes: string[]; companyStage: string[]; teamSize: string; pace: string };
}

export interface UserProfile {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  timezone: string;
  linkedin: string;
  portfolio: string;
  bio: string;
  yearsExperience: number;
  currentCompany: string;
  pitch: string;
}

/** The signed-in user as the backend knows them (GET /user/me). */
export interface CurrentUser {
  user_id: number;
  user_email: string;
}

export interface CompanyFilters {
  /** Where the company is hiring (Apollo organization_job_locations). */
  hiring_locations: string[];
  /** Where the company is headquartered; only set when the query asks for it. */
  company_locations: string[];
  employee_ranges: string[];
  keyword_tags: string[];
  market_segments: string[];
  job_title_signals: string[];
  min_active_job_postings: number | null;
  job_posted_within_days: number | null;
  founded_year_min: number | null;
  founded_year_max: number | null;
}

export interface CompanyRow {
  apollo_org_id: string;
  company_name: string;
  domain: string | null;
  linkedin_url: string | null;
  linkedin_jobs_url: string | null;
  logo_url: string | null;
  founded_year: number | null;
}

export interface CompanySearchPage {
  query: string;
  filters: CompanyFilters;
  page: number;
  rows: CompanyRow[];
  total_entries: number | null;
  has_more: boolean;
  credits_left: number;
  used_profile: boolean;
}

export interface JobPosting {
  title: string;
  url: string | null;
  location: string | null;
  posted_at: string | null;
  matches_role: boolean;
}

export interface JobPostings {
  org_id: string;
  postings: JobPosting[];
  matched_count: number;
  total: number;
  credits_left: number;
}

export type OutreachStatus = "searching" | "ready" | "no_contacts" | "failed";

export interface OutreachCompany {
  apollo_org_id: string;
  status: OutreachStatus;
  contacts_found: number;
  error: string | null;
  searched_at: string;
}
