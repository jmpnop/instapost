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
│                 │     │    (Python)     │     │    Database     │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │  Dropbox  │ │ Instagram │ │  Stripe   │
            │    API    │ │ Graph API │ │    API    │
            └───────────┘ └───────────┘ └───────────┘
```

### 2.2 Component Overview

| Component | Technology | Purpose |
|-----------|------------|---------|
| Bot Application | Python 3.13+ / python-telegram-bot | Core bot logic, command handling |
| Database | PostgreSQL 15+ | User data, subscriptions, schedules |
| Cache | Redis | Session management, rate limiting |
| Task Queue | Celery + Redis | Background job processing |
| Payment Processing | Stripe | Subscription billing |
| File Storage | Dropbox API | Image hosting for Instagram |
| Instagram API | Facebook Graph API | Post publishing |

### 2.3 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Podman Compose                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Bot        │  │  Celery     │  │  Celery Beat        │  │
│  │  Container  │  │  Worker(s)  │  │  (Scheduler)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  PostgreSQL │  │    Redis    │  │  Nginx (optional)   │  │
│  │             │  │             │  │  for webhooks       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Why Podman over Docker:**
- Daemonless architecture (no root daemon required)
- Rootless containers by default (better security)
- Drop-in replacement for Docker CLI
- Native systemd integration
- OCI-compliant

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
    status: str                      # active/cancelled/past_due/trialing
    stripe_subscription_id: str | None  # None for free and F&F
    stripe_customer_id: str | None
    current_period_start: datetime
    current_period_end: datetime       # For F&F: set to far future (2099-12-31)
    cancel_at_period_end: bool
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

### 4.3 Payment Flow (Stripe Integration)

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
┌───────────────────┐
│ Generate Stripe   │
│ Checkout Session  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Send payment link │
│ to user           │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ User completes    │
│ payment on Stripe │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Webhook callback  │
│ updates DB        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Notify user of    │
│ successful upgrade│
└───────────────────┘
```

### 4.4 Stripe Webhook Events to Handle

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Activate subscription |
| `invoice.paid` | Renew subscription period |
| `invoice.payment_failed` | Mark as past_due, notify user |
| `customer.subscription.updated` | Update plan details |
| `customer.subscription.deleted` | Downgrade to free |

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

### 6.1 Celery Tasks

```python
# tasks.py

@celery.task(bind=True, max_retries=3)
def process_scheduled_post(self, post_id: int):
    """Process a scheduled post at its designated time."""
    try:
        post = get_post(post_id)
        user = get_user(post.user_id)

        # Check user's quota
        if not check_quota(user):
            notify_user(user, "quota_exceeded")
            return

        # Upload to Dropbox
        dropbox_url = upload_to_dropbox(post.image_path, user)

        # Post to Instagram
        instagram_url = post_to_instagram(
            dropbox_url,
            post.caption,
            user.instagram_account
        )

        # Update post status
        mark_post_complete(post, instagram_url)

        # Notify user
        notify_user(user, "post_success", post=post, url=instagram_url)

        # Update usage
        increment_usage(user)

    except Exception as e:
        self.retry(countdown=60 * (2 ** self.request.retries))


@celery.task
def send_pre_post_notification(post_id: int):
    """Send notification before scheduled post."""
    post = get_post(post_id)
    user = get_user(post.user_id)

    if user.settings.notification_enabled:
        send_telegram_message(
            user.id,
            f"⏰ Reminder: Your post will be published in 15 minutes!\n\n"
            f"📷 {post.filename}\n"
            f"📱 {post.instagram_account}"
        )


@celery.task
def check_subscription_renewals():
    """Daily task to check and process subscription renewals."""
    expiring_soon = get_subscriptions_expiring_in(days=3)

    for sub in expiring_soon:
        notify_user(sub.user, "subscription_expiring", sub=sub)


@celery.task
def cleanup_expired_images():
    """Daily task to remove old uploaded images from Dropbox."""
    # Keep images for 7 days after posting
    old_posts = get_posts_older_than(days=7)

    for post in old_posts:
        delete_from_dropbox(post.dropbox_path)
        mark_image_cleaned(post)
```

### 6.2 Celery Beat Schedule

```python
CELERYBEAT_SCHEDULE = {
    'check-scheduled-posts': {
        'task': 'tasks.check_scheduled_posts',
        'schedule': 60.0,  # Every minute
    },
    'check-subscription-renewals': {
        'task': 'tasks.check_subscription_renewals',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'cleanup-expired-images': {
        'task': 'tasks.cleanup_expired_images',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'send-usage-reports': {
        'task': 'tasks.send_weekly_usage_reports',
        'schedule': crontab(day_of_week=0, hour=10),  # Sundays at 10 AM
    },
}
```

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
    status VARCHAR(20) DEFAULT 'active',
    stripe_subscription_id VARCHAR(255),  -- NULL for free and friends_family
    stripe_customer_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,  -- For F&F: 2099-12-31
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
```

### 7.2 Redis Keys Structure

```
# Session data
session:{user_id} -> {state, data, expires_at}

# Rate limiting
rate_limit:{user_id}:{action} -> count (expires)

# Locks for concurrent operations
lock:post:{post_id} -> 1 (with TTL)
lock:user:{user_id}:posting -> 1 (with TTL)

# Cache
cache:user:{user_id} -> {user_data}
cache:plan:{plan_name} -> {plan_limits}
cache:instagram:{account_id}:info -> {account_info}
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
| Payment Data | Stripe handles all PCI compliance |

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
4. **Stripe Webhook Failure**: Reconciliation job runs hourly

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
- [ ] Stripe integration
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

3. **Billing Currency**: USD only or support EUR, GBP?

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

# Database
DATABASE_URL=postgresql://user:pass@host:5432/instapost
REDIS_URL=redis://localhost:6379/0

# Stripe
STRIPE_SECRET_KEY=sk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_BASIC=price_xxx
STRIPE_PRICE_PRO=price_xxx
STRIPE_PRICE_BUSINESS=price_xxx

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

---

*Document Version: 1.1*
*Last Updated: 2025-12-30*
*Author: InstaPost Team*
