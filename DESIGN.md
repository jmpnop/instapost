# InstaPost Telegram Bot - Design Document

## 1. Executive Summary

This document outlines the design for transforming InstaPost from a single-user CLI tool into a multi-user Telegram bot with subscription-based monetization. The bot will allow users to schedule and automate Instagram posts through a conversational Telegram interface.

### Goals
- Replace CLI with intuitive Telegram bot interface
- Support multiple concurrent users with isolated data
- Implement tiered subscription model for monetization
- Maintain all existing functionality (scheduling, captions, validation)
- Ensure scalability, security, and reliability
- All features accessible via Telegram (analytics, bulk management, settings)

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Telegram API   │◄───►│  InstaPost Bot  │◄───►│   PostgreSQL    │
│  (+ Payments)   │     │    (Python)     │     │    Database     │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        │                 │
                        ▼                 ▼
                    ┌───────────┐     ┌───────────┐
                    │  Dropbox  │     │ Instagram │
                    │    API    │     │ Graph API │
                    └───────────┘     └───────────┘
```

### 2.2 Component Overview

| Component | Technology | Purpose |
|-----------|------------|---------|
| Bot Application | Python 3.13+ / python-telegram-bot | Core bot logic, command handling |
| Database | PostgreSQL 16+ | All data + cache + task queue + pub/sub |
| Task Queue | PostgreSQL (LISTEN/NOTIFY + task table) | Background job processing |
| Payment Processing | Telegram Payments (Stars + Crypto) | Subscription billing (native) |
| File Storage | Dropbox API | Image hosting for Instagram |
| Instagram API | Facebook Graph API | Post publishing |

**PostgreSQL replaces Redis** - single database for everything:
- **Cache**: UNLOGGED tables with TTL (faster, no WAL overhead)
- **Sessions**: JSONB column with expiration timestamps
- **Task Queue**: Task table + LISTEN/NOTIFY for workers
- **Rate Limiting**: Sliding window counters in PostgreSQL
- **Pub/Sub**: Native LISTEN/NOTIFY for real-time events

### 2.3 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Podman Compose                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Bot        │  │  Worker     │  │  Scheduler          │  │
│  │  Container  │  │  Container  │  │  (cron/pg_cron)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────────────────────┐  ┌─────────────────────┐  │
│  │         PostgreSQL          │  │  Nginx (optional)   │  │
│  │  (data + cache + queue)     │  │  for webhooks       │  │
│  └─────────────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Why Podman over Docker:**
- Daemonless architecture (no root daemon required)
- Rootless containers by default (better security)
- Drop-in replacement for Docker CLI
- Native systemd integration
- OCI-compliant

### 2.4 Detailed Architecture

#### 2.4.1 Actors

| Actor | Type | Role | Location |
|-------|------|------|----------|
| **End User** | Human | Instagram content creator using the bot | Anywhere (via Telegram) |
| **Admin** | Human | System operator, manages F&F users, monitors health | Via Telegram + server access |
| **Telegram** | External Service | Message relay, payments, file transfer | Telegram servers (cloud) |
| **Instagram/Facebook** | External Service | Content publishing platform | Meta servers (cloud) |
| **Dropbox** | External Service | Image hosting for public URLs | Dropbox servers (cloud) |

#### 2.4.2 Compute Entities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VPS / Cloud Server                                │
│                         (e.g., Hetzner, DigitalOcean)                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Podman Pod Network                              │ │
│  │                                                                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │   instapost  │  │   instapost  │  │   pg_cron    │                  │ │
│  │  │     -bot     │  │   -worker    │  │  (in postgres)│                  │ │
│  │  │              │  │              │  │              │                  │ │
│  │  │ Python 3.13  │  │ Python 3.13  │  │ PostgreSQL   │                  │ │
│  │  │ telegram-bot │  │ asyncio      │  │ extension    │                  │ │
│  │  │ library      │  │ task runner  │  │              │                  │ │
│  │  │              │  │              │  │              │                  │ │
│  │  │ Port: 8443   │  │ No ports     │  │ Runs inside  │                  │ │
│  │  │ (webhook)    │  │ exposed      │  │ PostgreSQL   │                  │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────┘                  │ │
│  │         │                 │                                             │ │
│  │         │                 │                                             │ │
│  │         │    TCP :5432    │    TCP :5432                                │ │
│  │         │   LISTEN/NOTIFY │   (polling + LISTEN)                        │ │
│  │         │                 │                                             │ │
│  │         └────────┬────────┘                                             │ │
│  │                  │                                                       │ │
│  │                  ▼                                                       │ │
│  │         ┌────────────────────────────────────────┐                      │ │
│  │         │            PostgreSQL 16+              │                      │ │
│  │         │        (Single Source of Truth)        │                      │ │
│  │         │                                        │                      │ │
│  │         │  TABLES:                               │                      │ │
│  │         │  ├── users, subscriptions, posts       │                      │ │
│  │         │  ├── task_queue (background jobs)      │                      │ │
│  │         │  ├── cache (UNLOGGED, with TTL)        │                      │ │
│  │         │  ├── sessions (JSONB + expiry)         │                      │ │
│  │         │  └── rate_limits (sliding window)      │                      │ │
│  │         │                                        │                      │ │
│  │         │  FEATURES USED:                        │                      │ │
│  │         │  ├── LISTEN/NOTIFY (pub/sub)           │                      │ │
│  │         │  ├── SKIP LOCKED (task claiming)       │                      │ │
│  │         │  ├── pg_cron (periodic tasks)          │                      │ │
│  │         │  └── JSONB (flexible data)             │                      │ │
│  │         │                                        │                      │ │
│  │         │  Port: 5432 (internal only)            │                      │ │
│  │         └────────────────────────────────────────┘                      │ │
│  │                                                                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Volumes (persistent storage on host):                                       │
│  ├── /var/lib/instapost/postgres/    → PostgreSQL data                      │
│  └── /var/lib/instapost/temp/        → Temporary image files                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Container | Process | CPU | Memory | Scaling |
|-----------|---------|-----|--------|---------|
| **instapost-bot** | Main bot (handles Telegram updates) | 1 core | 512MB | Single instance |
| **instapost-worker** | Background task processor (LISTEN/NOTIFY) | 0.5-1 core | 512MB | Horizontal (1-N workers) |
| **postgres** | Database + cache + queue + scheduler | 1-2 cores | 1GB | Single instance (or managed) |

**Simplified stack**: Only 2-3 containers instead of 5. PostgreSQL handles everything.

#### 2.4.3 Storage Entities

| Storage | Type | Location | Data Stored | Persistence |
|---------|------|----------|-------------|-------------|
| **PostgreSQL** | Relational DB | Container volume | Everything (see below) | Persistent (backed up) |
| **Dropbox** | Cloud storage | Dropbox servers | Posted images (temporary) | 7 days after posting |
| **Local temp** | Filesystem | Host volume | Images during processing | Cleared after upload |

**PostgreSQL stores all data:**
| Table Type | Purpose | PostgreSQL Feature |
|------------|---------|-------------------|
| Core tables | Users, subscriptions, posts, payments | Standard tables |
| Task queue | Background jobs waiting to run | `SELECT FOR UPDATE SKIP LOCKED` |
| Cache | Temporary data with TTL | UNLOGGED tables (no WAL = faster) |
| Sessions | User conversation state | JSONB + expiration timestamp |
| Rate limits | API call counters | Sliding window with timestamps |

#### 2.4.4 Communication Patterns

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL NETWORK (HTTPS)                          │
└─────────────────────────────────────────────────────────────────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   Telegram    │          │   Dropbox     │          │   Instagram   │
│   Bot API     │          │     API       │          │   Graph API   │
│               │          │               │          │               │
│ api.telegram  │          │ api.dropbox   │          │ graph.face    │
│ .org:443      │          │ .com:443      │          │ book.com:443  │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                           │                           │
        │ HTTPS (webhook)           │ HTTPS                     │ HTTPS
        │ or Long Polling           │                           │
        ▼                           ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INSTAPOST BOT                                   │
│                                                                              │
│   Outbound connections (bot initiates):                                     │
│   • Telegram API: Send messages, invoices, get file downloads               │
│   • Dropbox API: Upload images, create shared links                         │
│   • Instagram API: Create media containers, publish posts                   │
│                                                                              │
│   Inbound connections (external initiates):                                 │
│   • Telegram Webhook: Receives updates on port 8443 (HTTPS required)        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        │ Internal network (container-to-container)
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTERNAL POD NETWORK                               │
│                                                                              │
│  Communication Method: TCP sockets over Podman internal network             │
│  No ports exposed to internet (except bot webhook)                          │
│                                                                              │
│  ┌─────────────┐                              ┌─────────────┐               │
│  │  Bot        │                              │   Worker    │               │
│  │             │                              │             │               │
│  │  INSERT     │                              │  LISTEN     │               │
│  │  task into  │                              │  for new    │               │
│  │  task_queue │                              │  tasks      │               │
│  └──────┬──────┘                              └──────┬──────┘               │
│         │                                            │                      │
│         │ TCP :5432                                  │ TCP :5432            │
│         │ (INSERT + NOTIFY)                          │ (LISTEN + SELECT)    │
│         │                                            │                      │
│         └──────────────────┬─────────────────────────┘                      │
│                            ▼                                                 │
│         ┌───────────────────────────────────────────┐                       │
│         │             PostgreSQL :5432              │                       │
│         │                                           │                       │
│         │  ┌─────────────────────────────────────┐  │                       │
│         │  │  task_queue table                   │  │                       │
│         │  │  + LISTEN/NOTIFY channel            │  │                       │
│         │  │                                     │  │                       │
│         │  │  Bot: INSERT + pg_notify('tasks')   │  │                       │
│         │  │  Worker: LISTEN tasks + poll        │  │                       │
│         │  │  Worker: SELECT FOR UPDATE SKIP     │  │                       │
│         │  │          LOCKED (claim task)        │  │                       │
│         │  └─────────────────────────────────────┘  │                       │
│         │                                           │                       │
│         │  Also stores: users, posts, sessions,    │                       │
│         │  cache, rate_limits, payments            │                       │
│         └───────────────────────────────────────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 2.4.5 Communication Protocols

| Connection | Protocol | Port | Direction | Auth Method |
|------------|----------|------|-----------|-------------|
| User → Telegram | HTTPS | 443 | Outbound (user) | Telegram account |
| Telegram → Bot (webhook) | HTTPS | 8443 | Inbound | Webhook secret |
| Bot → Telegram API | HTTPS | 443 | Outbound | Bot token |
| Bot → Dropbox API | HTTPS | 443 | Outbound | OAuth2 refresh token |
| Bot → Instagram API | HTTPS | 443 | Outbound | Page access token |
| Bot → PostgreSQL | TCP | 5432 | Internal | Username/password |
| Worker → PostgreSQL | TCP | 5432 | Internal | Username/password |

**PostgreSQL-based task queue protocol:**
1. Bot inserts task into `task_queue` table
2. Bot calls `pg_notify('tasks', task_id)` to wake workers
3. Worker listens on channel: `LISTEN tasks`
4. Worker claims task: `SELECT * FROM task_queue WHERE status='pending' FOR UPDATE SKIP LOCKED LIMIT 1`
5. Worker processes task, updates status to 'completed' or 'failed'

#### 2.4.6 Data Flow: Posting an Image

```
 User                 Telegram           Bot            PostgreSQL        Worker         Dropbox        Instagram
   │                     │                │                 │               │               │               │
   │  1. Send image      │                │                 │               │               │               │
   │ ──────────────────► │                │                 │               │               │               │
   │                     │  2. Webhook    │                 │               │               │               │
   │                     │ ─────────────► │                 │               │               │               │
   │                     │                │  3. Download    │               │               │               │
   │                     │ ◄───────────── │     image       │               │               │               │
   │                     │                │                 │               │               │               │
   │                     │                │  4. Save to     │               │               │               │
   │                     │                │     temp file   │               │               │               │
   │                     │                │                 │               │               │               │
   │                     │                │  5. Validate    │               │               │               │
   │                     │                │     image       │               │               │               │
   │                     │                │                 │               │               │               │
   │                     │                │  6. INSERT post │               │               │               │
   │                     │                │     + task      │               │               │               │
   │                     │                │ ───────────────►│               │               │               │
   │                     │                │                 │               │               │               │
   │                     │                │  7. NOTIFY      │               │               │               │
   │                     │                │ ───────────────►│               │               │               │
   │                     │                │                 │  8. LISTEN    │               │               │
   │                     │                │                 │     wakes up  │               │               │
   │                     │                │                 │ ─────────────►│               │               │
   │                     │                │                 │               │               │               │
   │                     │                │                 │  9. SELECT    │               │               │
   │                     │                │                 │     FOR UPDATE│               │               │
   │                     │                │                 │     SKIP LOCKED               │               │
   │                     │                │                 │ ◄─────────────│               │               │
   │                     │                │                 │               │               │               │
   │                     │                │                 │               │  10. Upload   │               │
   │                     │                │                 │               │ ─────────────►│               │
   │                     │                │                 │               │               │               │
   │                     │                │                 │               │  11. Get link │               │
   │                     │                │                 │               │ ◄─────────────│               │
   │                     │                │                 │               │               │               │
   │                     │                │                 │               │  12. Create   │               │
   │                     │                │                 │               │      media    │               │
   │                     │                │                 │               │ ─────────────────────────────►│
   │                     │                │                 │               │               │               │
   │                     │                │                 │               │  13. Publish  │               │
   │                     │                │                 │               │ ─────────────────────────────►│
   │                     │                │                 │               │               │               │
   │                     │                │                 │  14. UPDATE   │               │               │
   │                     │                │                 │      status   │               │               │
   │                     │                │                 │ ◄─────────────│               │               │
   │                     │                │                 │               │               │               │
   │                     │  15. Notify    │                 │               │               │               │
   │                     │ ◄───────────── │     user        │               │               │               │
   │  16. Success msg    │                │                 │               │               │               │
   │ ◄────────────────── │                │                 │               │               │               │
   │                     │                │                 │               │               │               │
```

#### 2.4.7 Inter-Process Communication

| From | To | Mechanism | Data Format | Purpose |
|------|----|-----------|-------------|---------|
| Bot → Worker | PostgreSQL (task_queue + NOTIFY) | INSERT + pg_notify | SQL row + channel | Schedule background jobs |
| Worker → Bot | PostgreSQL (task_queue) | UPDATE status | SQL row | Task results, status updates |
| pg_cron → Worker | PostgreSQL (task_queue + NOTIFY) | INSERT + pg_notify | SQL row | Trigger periodic tasks |
| Bot → Bot | PostgreSQL (sessions table) | SELECT/UPDATE | JSONB | Session state |
| Bot → Bot | PostgreSQL (rate_limits table) | SELECT/UPDATE | SQL row | Rate limiting |

#### 2.4.8 Failure Modes & Recovery

| Component Failure | Impact | Recovery | Data Loss |
|-------------------|--------|----------|-----------|
| **Bot container dies** | No new messages processed | Auto-restart via Podman | None (stateless) |
| **Worker container dies** | Tasks queue up in PostgreSQL | Auto-restart, tasks retry | None (tasks persist in DB) |
| **PostgreSQL dies** | Complete service outage | Restore from backup | Up to last backup |
| **Network to Telegram** | Can't receive/send messages | Retry with backoff | Messages queued by Telegram |
| **Network to Dropbox** | Can't upload images | Task retry (5 attempts) | None (retry) |
| **Network to Instagram** | Can't publish posts | Task retry (5 attempts) | None (retry) |

**Advantage of PostgreSQL-only**: All state persists in one place. No split-brain scenarios between Redis and PostgreSQL.

#### 2.4.9 Deployment Topology Options

**Option A: Single VPS (Recommended)**
```
┌─────────────────────────────────┐
│         Single VPS              │
│  (2GB RAM, 1 CPU, 40GB SSD)    │
│                                 │
│  ├── instapost-bot              │
│  ├── instapost-worker           │
│  └── PostgreSQL                 │
│                                 │
│  Cost: ~$10-20/month            │
└─────────────────────────────────┘
```

**Option B: Managed PostgreSQL (Production)**
```
┌─────────────────┐         ┌─────────────────────┐
│   VPS           │         │ Managed PostgreSQL  │
│   (Bot +        │◄───────►│ (Supabase, Neon,    │
│   Worker)       │   TCP   │  Railway, etc.)     │
│                 │  :5432  │                     │
│ Cost: $5-10/mo  │         │ Cost: $0-25/mo      │
└─────────────────┘         └─────────────────────┘
```

**Simpler than before**: No Redis to manage. One database handles everything.

---

## 3. User Management

### 3.1 User Registration Flow

```
User sends /start
        │
        ▼
┌───────────────────┐
│ Check if user     │
│ exists in DB      │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
  [New]      [Existing]
    │           │
    ▼           │
┌─────────┐     │
│ Create  │     │
│ account │     │
│ (Free)  │     │
└────┬────┘     │
     │          │
     └────┬─────┘
          │
          ▼
┌───────────────────┐
│ Show main menu    │
│ with user's plan  │
└───────────────────┘
```

### 3.2 User Data Model

```python
class User:
    id: int                          # Telegram user ID (primary key)
    username: str | None             # Telegram username
    first_name: str                  # Telegram first name
    language_code: str               # Preferred language (en/ru)
    timezone: str                    # User's timezone (e.g., "America/New_York")
    created_at: datetime             # Registration timestamp
    is_active: bool                  # Account status
    is_banned: bool                  # Ban status
    is_admin: bool                   # Admin privileges
    is_friends_family: bool          # Friends & Family tier (free Business features)
    ff_granted_by: int | None        # Admin who granted F&F status
    ff_granted_at: datetime | None   # When F&F status was granted
    ff_note: str | None              # Admin note (e.g., "Brother", "College friend")

class InstagramAccount:
    id: int                          # Internal ID
    user_id: int                     # FK to User
    account_name: str                # Instagram username (display)
    business_account_id: str         # Instagram Business Account ID
    access_token: str                # Encrypted Facebook access token
    token_expires_at: datetime | None
    is_active: bool
    created_at: datetime

class UserSettings:
    user_id: int                     # FK to User (PK)
    default_instagram_account_id: int | None
    weekly_schedule: str             # JSON or cron-like format
    caption_template: str | None     # Default caption template
    auto_hashtags: str | None        # Default hashtags
    notification_enabled: bool       # Send notifications
    notification_time_before: int    # Minutes before post to notify
```

### 3.3 Multi-Account Support

Users on paid plans can connect multiple Instagram accounts:

| Plan | Max Instagram Accounts |
|------|----------------------|
| Free | 1 |
| Basic | 2 |
| Pro | 5 |
| Business | Unlimited |
| Friends & Family | Unlimited |

---

## 4. Subscription System

### 4.1 Subscription Tiers

| Feature | Free | Basic ($9/mo) | Pro ($29/mo) | Business ($99/mo) | Friends & Family |
|---------|------|---------------|--------------|-------------------|------------------|
| Posts per month | 10 | 100 | 500 | Unlimited | Unlimited |
| Instagram accounts | 1 | 2 | 5 | Unlimited | Unlimited |
| Scheduled posts queue | 5 | 25 | 100 | Unlimited | Unlimited |
| Caption templates | 1 | 5 | 20 | Unlimited | Unlimited |
| Image validation | Basic | Advanced | Advanced | Advanced | Advanced |
| Priority support | - | - | Yes | Yes | Yes |
| Analytics | - | Basic | Full | Full + Export | Full + Export |
| API access | - | - | - | Yes | Yes |
| Custom posting times | - | Yes | Yes | Yes | Yes |
| Bulk upload | - | - | 10 images | 50 images | 50 images |
| Price | $0 | $9/mo | $29/mo | $99/mo | $0 (invite only) |

**Friends & Family Tier:**
- Same features as Business tier
- Free of charge (no payment required)
- Invite-only: must be granted by system admin
- Cannot be self-selected during registration
- Managed via admin commands

### 4.2 Subscription Data Model

```python
class Subscription:
    id: int
    user_id: int                     # FK to User
    plan: str                        # free/basic/pro/business/friends_family
    status: str                      # active/cancelled/expired
    payment_method: str | None       # stars/crypto/None (for free/F&F)
    telegram_payment_id: str | None  # Telegram payment charge ID
    currency: str | None             # XTR (Stars), TON, USDT
    current_period_start: datetime
    current_period_end: datetime     # For F&F: set to far future (2099-12-31)
    auto_renew: bool                 # User preference for auto-renewal
    created_at: datetime
    updated_at: datetime

class UsageTracking:
    id: int
    user_id: int                     # FK to User
    period_start: date               # Start of billing period
    period_end: date                 # End of billing period
    posts_used: int                  # Posts published this period
    posts_limit: int                 # Limit for this period
    storage_used_mb: float           # Storage used
```

### 4.3 Payment Methods

Telegram-native payments only (no third-party accounts required):

| Method | How It Works | Platforms |
|--------|--------------|-----------|
| **Telegram Stars** | User buys Stars → pays bot → Telegram pays developer | All (iOS, Android, Desktop) |
| **Cryptocurrency** | User pays via @wallet → developer receives TON/USDT | All |

**Why Telegram-native only:**
- No merchant accounts to set up (Stripe, etc.)
- No payment provider fees to manage
- Telegram handles all payment processing
- Instant payouts via Fragment (Stars) or @wallet (Crypto)

### 4.4 Payment Flow

```
User selects /upgrade
        │
        ▼
┌───────────────────┐
│ Show plan options │
│ with prices       │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ User selects plan │
└─────────┬─────────┘
          │
          ▼
┌───────────────────────────┐
│ Choose payment method     │
│ [⭐ Stars] [💎 Crypto]    │
└─────────┬─────────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
[Stars]      [Crypto]
    │           │
    ▼           ▼
┌─────────┐ ┌─────────┐
│ Stars   │ │ TON/    │
│ Invoice │ │ USDT    │
└────┬────┘ └────┬────┘
     │           │
     └─────┬─────┘
           │
           ▼
┌───────────────────┐
│ User completes    │
│ payment in        │
│ Telegram          │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ PreCheckoutQuery  │
│ validation        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ SuccessfulPayment │
│ callback          │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Activate          │
│ subscription      │
└───────────────────┘
```

### 4.5 Payment Handlers

```python
# Handle pre-checkout query (validate before payment)
async def pre_checkout_handler(update: Update, context: ContextTypes):
    query = update.pre_checkout_query

    user = get_user(query.from_user.id)
    plan = query.invoice_payload  # e.g., "basic_monthly"

    if not validate_upgrade(user, plan):
        await query.answer(ok=False, error_message="Upgrade not available")
        return

    await query.answer(ok=True)


# Handle successful payment (Stars or Crypto)
async def successful_payment_handler(update: Update, context: ContextTypes):
    payment = update.message.successful_payment
    user_id = update.effective_user.id

    plan = payment.invoice_payload
    amount = payment.total_amount
    currency = payment.currency  # "XTR" for Stars
    charge_id = payment.telegram_payment_charge_id

    # Determine payment method
    payment_method = "stars" if currency == "XTR" else "crypto"

    # Activate subscription
    activate_subscription(
        user_id=user_id,
        plan=plan,
        payment_method=payment_method,
        telegram_payment_id=charge_id
    )

    await update.message.reply_text(
        f"✅ Payment successful! Your {plan} plan is now active."
    )


# Send Stars invoice
async def send_stars_invoice(chat_id: int, plan: str, context: ContextTypes):
    prices = {"basic": 450, "pro": 1450, "business": 4950}

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=f"InstaPost {plan.title()} Plan",
        description=f"Monthly subscription to {plan} plan",
        payload=f"{plan}_monthly",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice("Subscription", prices[plan])],
    )
```

### 4.6 Pricing

| Plan | Stars | TON | USDT |
|------|-------|-----|------|
| Basic | 450 ⭐ | ~1.5 TON | $9 |
| Pro | 1,450 ⭐ | ~5 TON | $29 |
| Business | 4,950 ⭐ | ~17 TON | $99 |

**Notes:**
- Stars: ~$0.02 per Star, Telegram takes 0% (Apple/Google take 30% when user buys Stars)
- Crypto: Network fees only (~0-1%), you receive TON/USDT directly to @wallet
- TON prices recalculated daily based on market rate
- Annual plans: 2 months free (pay for 10 months)

---

## 5. Telegram Bot Interface

### 5.1 Command Structure

#### Public Commands (shown in menu)
```
/start          - Start bot / Show main menu
/help           - Show help and documentation
/post           - Create a new post
/schedule       - Manage posting schedule
/queue          - View scheduled posts
/history        - View posting history
/account        - Manage Instagram account(s)
/settings       - Bot settings
/plan           - View current plan & usage
/upgrade        - Upgrade subscription
```

#### Admin Commands (hidden)
```
/admin_stats     - System statistics
/admin_users     - User management
/admin_ban       - Ban user
/admin_broadcast - Send message to all users

# Friends & Family Management
/admin_ff_add    - Grant F&F status to user
/admin_ff_remove - Revoke F&F status from user
/admin_ff_list   - List all F&F users
```

#### 5.1.1 Friends & Family Admin Workflows

**Granting F&F Status:**
```
Admin: /admin_ff_add
Bot: 👨‍👩‍👧‍👦 Grant Friends & Family Status

     Enter the user's Telegram ID or @username:

Admin: @johndoe
Bot: Found user:
     👤 John Doe (@johndoe)
     📱 ID: 123456789
     📅 Joined: 2025-01-10
     💎 Current plan: Free

     Add a note for this F&F member:
     (e.g., "Brother", "College roommate")

Admin: Best friend from college
Bot: ✅ F&F status granted to @johndoe

     👤 John Doe
     🎁 Plan: Friends & Family (Business features)
     📝 Note: Best friend from college
     ⏰ Granted: 2025-01-15

     [View F&F List] [Grant Another]
```

**Listing F&F Users:**
```
Admin: /admin_ff_list
Bot: 👨‍👩‍👧‍👦 Friends & Family Members (3 total)

     1. @johndoe (John Doe)
        📝 Best friend from college
        📅 Granted: 2025-01-15
        📊 Posts this month: 45

     2. @jane_smith (Jane Smith)
        📝 Sister
        📅 Granted: 2024-12-01
        📊 Posts this month: 12

     3. @mikebrown (Mike Brown)
        📝 Business partner
        📅 Granted: 2025-01-02
        📊 Posts this month: 78

     [Add New] [Export List]
```

**Revoking F&F Status:**
```
Admin: /admin_ff_remove
Bot: 👨‍👩‍👧‍👦 Remove F&F Status

     Select user to remove:
     [👤 @johndoe - John Doe]
     [👤 @jane_smith - Jane Smith]
     [👤 @mikebrown - Mike Brown]

Admin: [👤 @mikebrown - Mike Brown]
Bot: ⚠️ Confirm removing F&F status from:

     👤 Mike Brown (@mikebrown)
     📝 Note: Business partner
     📅 F&F since: 2025-01-02

     Their plan will be downgraded to Free.

     [Confirm Remove] [Cancel]

Admin: [Confirm Remove]
Bot: ✅ F&F status removed from @mikebrown

     User has been downgraded to Free plan.
     They will be notified of this change.
```

### 5.2 Conversation Flows

#### 5.2.1 Creating a Post (/post)

```
User: /post
Bot: 📸 Send me an image to post to Instagram.

     You can also send a caption with the image, or I'll ask for it next.

User: [Sends image]
Bot: ✅ Image received! (1080x1080, 245KB)

     📝 Now send me a caption for this post.

     Or choose an option:
     [Use template] [No caption] [Cancel]

User: Beautiful sunset! #photography #nature
Bot: 📋 Post Preview:

     📷 Image: sunset.jpg
     📝 Caption: Beautiful sunset! #photography #nature
     📅 Instagram: @username

     When should I post this?
     [Now] [Schedule] [Add to queue] [Cancel]

User: [Schedule]
Bot: 📅 Select date:
     [Today] [Tomorrow] [Pick date...]

User: [Tomorrow]
Bot: 🕐 Select time (Your timezone: America/New_York):
     [09:00] [12:00] [15:00] [18:00] [21:00] [Custom...]

User: [18:00]
Bot: ✅ Post scheduled!

     📷 sunset.jpg
     📅 Tomorrow at 6:00 PM (EST)
     📱 @username

     I'll notify you 15 minutes before posting.

     [View Queue] [Create Another] [Main Menu]
```

#### 5.2.2 Connecting Instagram Account (/account)

```
User: /account
Bot: 📱 Instagram Account Management

     Currently connected: @username (Active ✅)

     [Connect New Account] [Disconnect] [Refresh Token] [Back]

User: [Connect New Account]
Bot: 🔗 To connect your Instagram account, I need a Facebook Page Access Token.

     📋 Quick Guide:
     1. Go to Facebook Developer Console
     2. Create/select your app
     3. Generate a Page Access Token

     [📖 Detailed Instructions] [I have my token]

User: [I have my token]
Bot: 📝 Please send me your Facebook Page Access Token.

     ⚠️ Your token will be encrypted and stored securely.
     Never share this token with anyone else.

User: EAABsbCS1iHgBO...
Bot: 🔍 Validating token...

     ✅ Token valid!
     📱 Instagram Account: @newaccount
     📊 Followers: 1,234

     [Confirm Connection] [Cancel]

User: [Confirm Connection]
Bot: ✅ Instagram account @newaccount connected successfully!

     [Set as Default] [Back to Accounts]
```

### 5.3 Inline Keyboards & Callbacks

```python
# Main menu keyboard
MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📸 New Post", callback_data="post_new")],
    [InlineKeyboardButton("📋 Queue", callback_data="queue_view"),
     InlineKeyboardButton("📅 Schedule", callback_data="schedule_view")],
    [InlineKeyboardButton("📱 Account", callback_data="account_manage"),
     InlineKeyboardButton("⚙️ Settings", callback_data="settings_view")],
    [InlineKeyboardButton("💎 Upgrade", callback_data="plan_upgrade")]
])

# Callback data format: action_subaction_params
# Examples:
# - post_new
# - post_confirm_12345
# - queue_cancel_12345
# - schedule_edit_daily
# - plan_select_pro
```

### 5.4 Message Templates

```python
MESSAGES = {
    "en": {
        "welcome": """
👋 Welcome to InstaPost Bot!

I help you schedule and automate your Instagram posts.

🚀 Quick Start:
1. Connect your Instagram account with /account
2. Send me an image to create your first post
3. Choose when to publish - now or scheduled

Need help? Use /help for detailed instructions.
        """,
        "post_success": """
✅ Successfully posted to Instagram!

📷 {filename}
📱 {account}
🔗 {url}
⏰ {timestamp}
        """,
        "quota_exceeded": """
⚠️ You've reached your monthly post limit ({used}/{limit}).

Your limit resets on {reset_date}.

💎 Upgrade to {next_plan} for {next_limit} posts/month.
[Upgrade Now]
        """,
    },
    "ru": {
        # Russian translations...
    }
}
```

---

## 6. Background Job Processing

### Why PostgreSQL as Task Queue

PostgreSQL provides a robust, transactional task queue that eliminates the need for external systems like Redis/RabbitMQ:

| Feature | Benefit |
|---------|---------|
| **ACID compliance** | Tasks never lost, no duplicates, atomic state changes |
| **LISTEN/NOTIFY** | Real-time push notifications to workers (no polling delay) |
| **FOR UPDATE SKIP LOCKED** | Safe concurrent task claiming without race conditions |
| **JSONB payloads** | Flexible task data, queryable, indexable |
| **Rich SQL** | Query, filter, prioritize, retry logic all in SQL |
| **Row-level locking** | Multiple workers safely grab different tasks |
| **Single source of truth** | Task state and application data in same transaction |

**Trade-off**: Dedicated message brokers (RabbitMQ, Redis) handle higher throughput. PostgreSQL is ideal for moderate workloads (thousands of tasks/minute) - perfect for InstaPost's scale.

### 6.1 Worker Process

```python
# worker.py - Async worker using PostgreSQL LISTEN/NOTIFY

import asyncio
import asyncpg
from datetime import datetime

class TaskWorker:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.handlers = {
            'post_to_instagram': self.handle_post_to_instagram,
            'send_notification': self.handle_send_notification,
            'cleanup_images': self.handle_cleanup_images,
            'send_expiry_reminder': self.handle_expiry_reminder,
        }

    async def run(self):
        """Main worker loop."""
        self.conn = await asyncpg.connect(self.db_url)

        # Listen for new task notifications
        await self.conn.add_listener('new_task', self.on_new_task)

        print("Worker started, listening for tasks...")

        # Also poll periodically (in case NOTIFY is missed)
        while True:
            await self.process_pending_tasks()
            await asyncio.sleep(5)  # Poll every 5 seconds

    def on_new_task(self, conn, pid, channel, payload):
        """Called when new task is inserted."""
        asyncio.create_task(self.process_pending_tasks())

    async def process_pending_tasks(self):
        """Claim and process pending tasks."""
        while True:
            # Claim one task atomically
            task = await self.conn.fetchrow('''
                UPDATE task_queue
                SET status = 'running', started_at = NOW()
                WHERE id = (
                    SELECT id FROM task_queue
                    WHERE status = 'pending'
                      AND scheduled_for <= NOW()
                      AND attempts < max_attempts
                    ORDER BY priority DESC, scheduled_for ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
            ''')

            if not task:
                break  # No more tasks

            await self.execute_task(task)

    async def execute_task(self, task):
        """Execute a single task with error handling."""
        try:
            handler = self.handlers.get(task['task_type'])
            if handler:
                await handler(task['payload'])

            # Mark completed
            await self.conn.execute('''
                UPDATE task_queue
                SET status = 'completed', completed_at = NOW()
                WHERE id = $1
            ''', task['id'])

        except Exception as e:
            # Mark failed, increment attempts
            await self.conn.execute('''
                UPDATE task_queue
                SET status = CASE
                        WHEN attempts + 1 >= max_attempts THEN 'failed'
                        ELSE 'pending'
                    END,
                    attempts = attempts + 1,
                    last_error = $2,
                    scheduled_for = NOW() + INTERVAL '1 minute' * attempts
                WHERE id = $1
            ''', task['id'], str(e))

    async def handle_post_to_instagram(self, payload: dict):
        """Process a scheduled Instagram post."""
        post_id = payload['post_id']
        post = await self.get_post(post_id)
        user = await self.get_user(post['user_id'])

        # Check quota
        if not await self.check_quota(user):
            await self.notify_user(user['id'], "quota_exceeded")
            return

        # Upload to Dropbox
        dropbox_url = await self.upload_to_dropbox(post['image_path'])

        # Post to Instagram
        instagram_url = await self.post_to_instagram(
            dropbox_url, post['caption'], user['instagram_account_id']
        )

        # Update post status
        await self.conn.execute('''
            UPDATE posts SET status = 'completed', instagram_url = $2
            WHERE id = $1
        ''', post_id, instagram_url)

        # Notify user
        await self.notify_user(user['id'], f"✅ Posted! {instagram_url}")

    # ... other handlers ...
```

### 6.2 Enqueuing Tasks

```python
# From the bot, enqueue a task:

async def enqueue_task(
    conn: asyncpg.Connection,
    task_type: str,
    payload: dict,
    scheduled_for: datetime = None,
    priority: int = 0
):
    """Add a task to the queue. NOTIFY is triggered automatically."""
    await conn.execute('''
        INSERT INTO task_queue (task_type, payload, scheduled_for, priority)
        VALUES ($1, $2, COALESCE($3, NOW()), $4)
    ''', task_type, payload, scheduled_for, priority)


# Example usage in bot:
await enqueue_task(conn, 'post_to_instagram', {'post_id': 123})
await enqueue_task(conn, 'send_notification', {'user_id': 456, 'message': 'Hello!'})
```

### 6.3 Periodic Tasks (via pg_cron)

Periodic tasks are scheduled in PostgreSQL using pg_cron extension (see section 7.3).

| Task | Schedule | Description |
|------|----------|-------------|
| `check-scheduled-posts` | Every minute | Queue posts that are due |
| `cleanup-cache` | Hourly | Delete expired cache entries |
| `cleanup-sessions` | Hourly | Delete expired sessions |
| `cleanup-rate-limits` | Hourly | Delete old rate limit entries |
| `subscription-reminders` | Daily 9 AM | Notify users of expiring subscriptions |

---

## 7. Database Schema

### 7.1 PostgreSQL Tables

```sql
-- Users table
CREATE TABLE users (
    id BIGINT PRIMARY KEY,              -- Telegram user ID
    username VARCHAR(255),
    first_name VARCHAR(255) NOT NULL,
    language_code VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_banned BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_friends_family BOOLEAN DEFAULT FALSE,
    ff_granted_by BIGINT REFERENCES users(id),
    ff_granted_at TIMESTAMP,
    ff_note VARCHAR(255)
);

-- Instagram accounts
CREATE TABLE instagram_accounts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    account_name VARCHAR(255) NOT NULL,
    business_account_id VARCHAR(255) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    token_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, business_account_id)
);

-- User settings
CREATE TABLE user_settings (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    default_instagram_account_id INT REFERENCES instagram_accounts(id),
    weekly_schedule JSONB DEFAULT '{}',
    caption_template TEXT,
    auto_hashtags TEXT,
    notification_enabled BOOLEAN DEFAULT TRUE,
    notification_time_before INT DEFAULT 15
);

-- Subscriptions
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(20) DEFAULT 'free',  -- free/basic/pro/business/friends_family
    status VARCHAR(20) DEFAULT 'active',  -- active/cancelled/expired
    payment_method VARCHAR(20),  -- stars/crypto/NULL (for free/F&F)
    telegram_payment_id VARCHAR(255),  -- Telegram payment charge ID
    currency VARCHAR(10),  -- XTR (Stars), TON, USDT
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,  -- For F&F: 2099-12-31
    auto_renew BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment transactions (history of all payments)
CREATE TABLE payment_transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INT REFERENCES subscriptions(id),
    amount INT NOT NULL,  -- Stars or crypto smallest units
    currency VARCHAR(10) NOT NULL,  -- XTR (Stars), TON, USDT
    payment_method VARCHAR(20) NOT NULL,  -- stars/crypto
    telegram_payment_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'completed',  -- completed/refunded
    refund_id VARCHAR(255),  -- If refunded via Telegram
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Usage tracking
CREATE TABLE usage_tracking (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    posts_used INT DEFAULT 0,
    posts_limit INT NOT NULL,
    storage_used_mb FLOAT DEFAULT 0,
    UNIQUE(user_id, period_start)
);

-- Scheduled posts
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    instagram_account_id INT REFERENCES instagram_accounts(id),
    image_path TEXT NOT NULL,
    dropbox_path TEXT,
    caption TEXT,
    scheduled_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending/processing/completed/failed/cancelled
    instagram_url TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Caption templates
CREATE TABLE caption_templates (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    template TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_posts_user_status ON posts(user_id, status);
CREATE INDEX idx_posts_scheduled_time ON posts(scheduled_time) WHERE status = 'pending';
CREATE INDEX idx_usage_user_period ON usage_tracking(user_id, period_start);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_users_friends_family ON users(is_friends_family) WHERE is_friends_family = TRUE;
CREATE INDEX idx_payment_transactions_user ON payment_transactions(user_id, created_at DESC);
```

### 7.2 PostgreSQL Tables for Queue, Cache, Sessions

```sql
-- Task queue (replaces Celery + Redis)
CREATE TABLE task_queue (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,  -- 'post_to_instagram', 'cleanup_images', etc.
    payload JSONB NOT NULL,          -- Task arguments
    status VARCHAR(20) DEFAULT 'pending',  -- pending/running/completed/failed
    priority INT DEFAULT 0,          -- Higher = more urgent
    scheduled_for TIMESTAMP DEFAULT NOW(),  -- When to run
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 5,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_queue_pending ON task_queue(scheduled_for)
    WHERE status = 'pending';

-- Function to notify workers of new tasks
CREATE OR REPLACE FUNCTION notify_new_task() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('new_task', NEW.id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER task_notify AFTER INSERT ON task_queue
    FOR EACH ROW EXECUTE FUNCTION notify_new_task();


-- Session storage (replaces Redis sessions)
CREATE TABLE sessions (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    state VARCHAR(50),               -- Current conversation state
    data JSONB DEFAULT '{}',         -- State-specific data
    expires_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_expires ON sessions(expires_at);


-- Cache table (UNLOGGED = faster, no WAL, lost on crash - OK for cache)
CREATE UNLOGGED TABLE cache (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_cache_expires ON cache(expires_at);


-- Rate limiting (sliding window)
CREATE TABLE rate_limits (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,     -- 'post_create', 'image_upload', etc.
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, action, timestamp)
);

CREATE INDEX idx_rate_limits_window ON rate_limits(user_id, action, timestamp);

-- Clean up old rate limit entries (run via pg_cron)
-- DELETE FROM rate_limits WHERE timestamp < NOW() - INTERVAL '1 hour';


-- Advisory locks for distributed locking (replaces Redis locks)
-- Usage: SELECT pg_advisory_lock(hashtext('post:123'));
-- Usage: SELECT pg_advisory_unlock(hashtext('post:123'));
-- Or with timeout: SELECT pg_try_advisory_lock(hashtext('post:123'));
```

### 7.3 pg_cron Scheduled Jobs

```sql
-- Enable pg_cron extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Check for scheduled posts every minute
SELECT cron.schedule('check-scheduled-posts', '* * * * *', $$
    INSERT INTO task_queue (task_type, payload)
    SELECT 'post_to_instagram', jsonb_build_object('post_id', id)
    FROM posts
    WHERE status = 'pending'
      AND scheduled_time <= NOW()
      AND NOT EXISTS (
          SELECT 1 FROM task_queue
          WHERE task_type = 'post_to_instagram'
            AND payload->>'post_id' = posts.id::text
            AND status IN ('pending', 'running')
      );
$$);

-- Clean up expired cache entries every hour
SELECT cron.schedule('cleanup-cache', '0 * * * *', $$
    DELETE FROM cache WHERE expires_at < NOW();
$$);

-- Clean up expired sessions every hour
SELECT cron.schedule('cleanup-sessions', '0 * * * *', $$
    DELETE FROM sessions WHERE expires_at < NOW();
$$);

-- Clean up old rate limit entries every hour
SELECT cron.schedule('cleanup-rate-limits', '0 * * * *', $$
    DELETE FROM rate_limits WHERE timestamp < NOW() - INTERVAL '1 hour';
$$);

-- Send subscription expiry reminders daily at 9 AM
SELECT cron.schedule('subscription-reminders', '0 9 * * *', $$
    INSERT INTO task_queue (task_type, payload)
    SELECT 'send_expiry_reminder', jsonb_build_object('user_id', user_id)
    FROM subscriptions
    WHERE current_period_end BETWEEN NOW() AND NOW() + INTERVAL '3 days'
      AND status = 'active';
$$);
```

---

## 8. Security Considerations

### 8.1 Data Protection

| Data Type | Protection Method |
|-----------|-------------------|
| Access Tokens | AES-256 encryption at rest |
| User Data | PostgreSQL row-level security |
| API Keys | Environment variables, never in code |
| Passwords | Not applicable (Telegram auth) |
| Payment Data | Telegram handles all payment processing |

### 8.2 Rate Limiting

```python
RATE_LIMITS = {
    "post_create": {"requests": 10, "period": 60},      # 10 per minute
    "image_upload": {"requests": 20, "period": 60},     # 20 per minute
    "api_general": {"requests": 100, "period": 60},     # 100 per minute
    "account_connect": {"requests": 5, "period": 3600}, # 5 per hour
}
```

### 8.3 Input Validation

```python
# Image validation
MAX_IMAGE_SIZE_MB = 8
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png']
MIN_DIMENSION = 320
MAX_DIMENSION = 1440

# Text validation
MAX_CAPTION_LENGTH = 2200  # Instagram limit
MAX_HASHTAGS = 30          # Instagram limit

# Token validation
def validate_access_token(token: str) -> bool:
    # Verify format
    # Check with Facebook API
    # Validate permissions
    pass
```

### 8.4 Audit Logging

All sensitive operations are logged:
- Account connections/disconnections
- Subscription changes
- Post creations/deletions
- Settings changes
- Admin actions

---

## 9. Error Handling & Resilience

### 9.1 Error Categories

```python
class InstaPostError(Exception):
    """Base exception for all InstaPost errors."""
    pass

class QuotaExceededError(InstaPostError):
    """User has exceeded their plan's limits."""
    pass

class InstagramAPIError(InstaPostError):
    """Error from Instagram/Facebook API."""
    pass

class DropboxAPIError(InstaPostError):
    """Error from Dropbox API."""
    pass

class ValidationError(InstaPostError):
    """Input validation failed."""
    pass

class PaymentError(InstaPostError):
    """Payment processing failed."""
    pass
```

### 9.2 Retry Strategy

```python
RETRY_CONFIG = {
    "instagram_api": {
        "max_retries": 5,
        "initial_delay": 2,
        "backoff_factor": 1.5,
        "max_delay": 60,
        "retryable_errors": [429, 500, 502, 503, 504]
    },
    "dropbox_api": {
        "max_retries": 3,
        "initial_delay": 1,
        "backoff_factor": 2,
        "max_delay": 30,
    },
    "telegram_api": {
        "max_retries": 3,
        "initial_delay": 0.5,
        "backoff_factor": 2,
        "max_delay": 10,
    }
}
```

### 9.3 Fallback Mechanisms

1. **Post Scheduling Failure**: Queue for retry, notify user after 3 failures
2. **Database Connection Loss**: Reconnect with exponential backoff
3. **Redis Unavailable**: Fall back to in-memory cache (degraded mode)
4. **Payment Verification**: Daily job validates subscription status with Telegram

---

## 10. Monitoring & Analytics

### 10.1 Metrics to Track

**System Metrics:**
- Bot response time (p50, p95, p99)
- Task queue length and processing time
- Database connection pool usage
- Memory and CPU usage
- Error rates by type

**Business Metrics:**
- Daily/Weekly/Monthly active users
- Posts created and published
- Subscription conversions (free → paid)
- Churn rate by plan
- Revenue (MRR, ARR)

**User Metrics:**
- Posts per user
- Schedule adherence
- Feature usage

### 10.2 Alerting Rules

| Metric | Warning | Critical |
|--------|---------|----------|
| Error rate | > 1% | > 5% |
| Response time (p95) | > 2s | > 5s |
| Task queue length | > 1000 | > 5000 |
| Failed posts | > 10/hour | > 50/hour |
| Payment failures | > 5% | > 15% |

### 10.3 Logging Format

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "service": "instapost-bot",
  "user_id": 123456789,
  "action": "post_created",
  "post_id": 12345,
  "instagram_account": "username",
  "scheduled_time": "2025-01-15T18:00:00Z",
  "duration_ms": 150,
  "metadata": {
    "image_size": 245000,
    "caption_length": 120
  }
}
```

---

## 11. Localization

### 11.1 Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English | en | Primary |
| Russian | ru | Full support |
| Spanish | es | Planned |
| Portuguese | pt | Planned |

### 11.2 Translation Structure

```
locales/
├── en/
│   ├── messages.json      # UI messages
│   ├── errors.json        # Error messages
│   └── emails.json        # Email templates
├── ru/
│   ├── messages.json
│   ├── errors.json
│   └── emails.json
```

### 11.3 Date/Time Formatting

- Dates displayed in user's timezone
- Format based on locale (MM/DD vs DD/MM)
- Relative times for recent events ("5 minutes ago")

---

## 12. Migration Path from CLI

### 12.1 Phase 1: Parallel Operation (Week 1-2)
- Deploy bot alongside existing CLI
- CLI users can optionally connect Telegram
- Data migration tools for existing users

### 12.2 Phase 2: Feature Parity (Week 3-4)
- All CLI features available in bot
- Deprecation notice in CLI
- Documentation updated

### 12.3 Phase 3: CLI Deprecation (Week 5-6)
- CLI enters maintenance mode
- New features only in bot
- Migration deadline communicated

### 12.4 Phase 4: Full Transition (Week 7+)
- CLI removed or archived
- All users on bot platform
- Legacy data archived

---

## 13. Development Roadmap

### Phase 1: MVP (4 weeks)
- [ ] Basic bot framework
- [ ] User registration
- [ ] Single Instagram account connection
- [ ] Manual posting
- [ ] Basic scheduling
- [ ] Free tier only

### Phase 2: Subscriptions (2 weeks)
- [ ] Telegram Payments integration (Stars + Crypto)
- [ ] Subscription tiers
- [ ] Usage tracking
- [ ] Payment management

### Phase 3: Multi-Account (2 weeks)
- [ ] Multiple Instagram accounts
- [ ] Account switching
- [ ] Per-account settings

### Phase 4: Advanced Features (3 weeks)
- [ ] Caption templates
- [ ] Bulk upload
- [ ] Analytics dashboard
- [ ] Admin panel

### Phase 5: Polish & Scale (2 weeks)
- [ ] Performance optimization
- [ ] Additional languages
- [ ] Documentation
- [ ] Marketing website

---

## 14. Cost Estimation

### 14.1 Infrastructure Costs (Monthly)

| Service | Estimated Cost |
|---------|---------------|
| VPS (4GB RAM, 2 CPU) | $20-40 |
| PostgreSQL (Managed) | $15-30 |
| Redis (Managed) | $10-20 |
| Dropbox API | Based on storage |
| Domain + SSL | $1-2 |
| **Total** | **$50-100/month** |

### 14.2 Break-Even Analysis

With $75/month infrastructure cost:
- Need ~9 Basic subscribers ($9 × 9 = $81), or
- Need ~3 Pro subscribers ($29 × 3 = $87), or
- Need ~1 Business subscriber ($99)

---

## 15. Open Questions

1. **Dropbox vs AWS S3**: Should we migrate to S3 for better scalability and pricing?

2. **Webhook vs Polling**: Telegram supports both - webhook for production, polling for development?

3. **Stars vs Crypto**: Should we prioritize Stars (simpler) or offer both from day one?

4. **Refund Policy**: What's the refund window for subscriptions?

5. **Rate Limits**: How aggressive should free tier limits be?

6. **Video Support**: Timeline for Instagram Reels/Video support?

7. **Team Accounts**: Business plan with multiple team members?

---

## 16. Appendix

### A. Environment Variables

```bash
# Telegram
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_WEBHOOK_URL=https://...

# Database (PostgreSQL handles everything - data, cache, queue, sessions)
DATABASE_URL=postgresql://user:pass@host:5432/instapost

# Telegram Payments (native - no third-party accounts needed)
# Stars and Crypto via @wallet are both native to Telegram

# Pricing in Stars
PRICE_BASIC_STARS=450
PRICE_PRO_STARS=1450
PRICE_BUSINESS_STARS=4950

# Dropbox
DROPBOX_APP_KEY=xxx
DROPBOX_APP_SECRET=xxx

# Security
ENCRYPTION_KEY=xxx
SECRET_KEY=xxx

# Monitoring
SENTRY_DSN=xxx
```

### B. API Endpoints (Future REST API)

```
POST   /api/v1/posts              # Create post
GET    /api/v1/posts              # List posts
GET    /api/v1/posts/{id}         # Get post
DELETE /api/v1/posts/{id}         # Cancel post
GET    /api/v1/accounts           # List Instagram accounts
POST   /api/v1/accounts           # Connect account
DELETE /api/v1/accounts/{id}      # Disconnect account
GET    /api/v1/usage              # Get usage stats
GET    /api/v1/subscription       # Get subscription info
```

### C. Telegram Bot API Methods Used

- `sendMessage` - Send text messages
- `sendPhoto` - Send images
- `editMessageText` - Edit messages
- `editMessageReplyMarkup` - Update buttons
- `answerCallbackQuery` - Acknowledge button press
- `deleteMessage` - Remove messages
- `getFile` - Download uploaded images
- `setMyCommands` - Set command menu
- `sendInvoice` - Send payment invoice (Stars/Crypto)
- `answerPreCheckoutQuery` - Validate payment before processing
- `createInvoiceLink` - Generate shareable payment link

---

*Document Version: 1.1*
*Last Updated: 2025-12-30*
*Author: InstaPost Team*
