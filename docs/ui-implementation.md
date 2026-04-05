# Camille UI Implementation Plan
# Carbon Design System - Full Frontend

## Overview

A multi-role admin console built with IBM Carbon Design System v11 (`@carbon/react`).
Roles: `admin` (Camille platform), `org_manager` (MGA admin), `org_underwriter`.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | Vite + React 18 + TypeScript (strict) | Fast dev server; no Next.js needed |
| UI Library | `@carbon/react` v11 | IBM Carbon Design System; enterprise look |
| Icons | `@carbon/icons-react` | Carbon icon set |
| Router | React Router v6 | SPA routing |
| Server State | TanStack Query v5 | Caching, mutations, polling |
| HTTP | Axios | Interceptors for JWT refresh |
| Charts | `@carbon/charts-react` | Carbon-native charts (radar, bar) |
| Forms | React Hook Form | Validation + controlled inputs |
| Date | date-fns | Lightweight date formatting |

---

## Org Tiers

From business plan - tiers control assessment limits and features:

| Tier ID | Name | Pricing | Limits | Features |
|---|---|---|---|---|
| `tier_1` | Starter | $500-$1,500 / assessment | 10 assessments/month | Basic governance score; uploaded docs only |
| `tier_2` | Professional | $2,000-$5,000 / assessment | 50 assessments/month | Full report + external signals + litigation data |
| `enterprise` | Enterprise | $50K-$200K / year | Unlimited | All features + carrier weight config + priority support |
| `demo` | Demo (Internal) | Free | Unlimited | Admin override; no billing; for demos/testing |

Backend changes needed: add `tier` (string, default `tier_1`) and `is_demo` (bool, default false) to `organizations` table.

---

## User Flow

### New Org Onboarding
1. Admin logs in at `/admin`
2. Admin sends invitation to org manager email via `/admin/invite`
3. Org manager receives email with token link: `/signup?token=<token>`
4. Org manager fills: name, password, org name, org industry, selects tier
5. Account + org created in one transaction
6. Redirected to org manager dashboard

### Underwriter Onboarding
1. Org manager logs in, goes to `/team`
2. Invites underwriter email
3. Underwriter receives link: `/signup?token=<token>` (role pre-set to `org_underwriter`)
4. Underwriter fills: name, password only (org already set from invitation)
5. Redirected to underwriter dashboard

### Assessment Workflow
1. User (manager or underwriter) clicks "New Assessment"
2. Step 1: Enter assessed company name + optional config
3. Step 2: Upload governance documents (drag-and-drop, multiple files)
4. Step 3: Review + Launch pipeline
5. Redirected to assessment detail page with live status polling
6. When complete: view scores, flags, evidence, download PDF

---

## Page Map

### Public Pages
| Route | Page | Notes |
|---|---|---|
| `/login` | Login | Email + password; JWT stored in memory + httpOnly cookie |
| `/reset-password` | Request Reset | Enter email; receive 6-digit code |
| `/reset-password/confirm` | Confirm Reset | Enter code + new password |
| `/signup` | Accept Invitation | Via `?token=` param; role-aware form |

### Admin Pages (role: admin)
| Route | Page | Notes |
|---|---|---|
| `/admin` | Admin Dashboard | Org list, system stats |
| `/admin/organizations` | Org Management | List, search, view, toggle demo flag |
| `/admin/organizations/invite` | Invite Org Manager | Send invitation email |
| `/admin/users` | All Users | Search, deactivate |

### Shared Auth Shell (org_manager + org_underwriter)
| Route | Page | Visible to |
|---|---|---|
| `/dashboard` | Dashboard | Both; manager sees org stats, underwriter sees own stats |
| `/assessments` | Assessment List | Manager: all org; Underwriter: own only |
| `/assessments/new` | New Assessment | Both |
| `/assessments/:id` | Assessment Detail | Both (underwriter only if owns it) |
| `/team` | Team Management | Manager only |
| `/settings` | Settings | Both (manager has org settings tab) |
| `/billing` | Billing + Usage | Manager only |

---

## Page Specifications

### Login Page (`/login`)
- Carbon `Form` with `TextInput` (email) + `PasswordInput`
- "Forgot password?" link to `/reset-password`
- Submit calls `POST /api/v1/auth/login`; stores JWT in memory, sets refresh cookie
- Redirects to `/dashboard` on success
- Shows `InlineNotification` on error

### Password Reset Request (`/reset-password`)
- Email input + "Send Code" button
- Calls `POST /api/v1/auth/password-reset/request`
- On success: shows inline notification + redirects to `/reset-password/confirm`
- Shows generic "If email exists, code sent" message (no email enumeration)

### Password Reset Confirm (`/reset-password/confirm`)
- 6-digit code input + new password + confirm password
- Calls `POST /api/v1/auth/password-reset/confirm`
- On success: redirect to `/login` with success notification

### Invitation Signup (`/signup?token=<token>`)
- Validates token on mount (`GET /api/v1/auth/invitation-info?token=<token>`)
- Shows: "You have been invited to join [Org Name] as [Role]"
- For `org_manager` invitations (no org yet): shows full form including org creation:
  - First name, last name, email (pre-filled from invitation, readonly)
  - Password + confirm
  - Org name, industry, employee count range, AI systems count range
  - Tier selection: Carbon `RadioButtonGroup` showing tier cards with features + pricing
  - Demo mode note: "Your account has been configured for demo access"
- For `org_underwriter` invitations: shorter form (name + password only)
- Submits to `POST /api/v1/auth/signup`

### Admin Dashboard (`/admin`)
- Carbon `Grid` with stat tiles: total orgs, total users, assessments this month
- `DataTable` of recent organizations with tier badge + status

### Org Manager Dashboard (`/dashboard` for manager)
- Top stats row: assessments this month, credits used, remaining quota
- Recent assessments `DataTable` with risk tier badge + status tag
- Quick action: "New Assessment" button

### Underwriter Dashboard (`/dashboard` for underwriter)
- My assessments list with status + score
- "New Assessment" prominent button

### Assessment List (`/assessments`)
- `Tabs`: All | In Progress | Complete | Failed
- `DataTable`: company name, created date, status tag, risk tier badge, score, actions
- "New Assessment" button top-right
- Search/filter: by status, risk tier, date range
- Row click navigates to `/assessments/:id`

### New Assessment (`/assessments/new`)
Carbon `ProgressIndicator` multi-step:

**Step 1: Company Info**
- Company name, industry, optional notes
- Assessment config (advanced: dimension weight overrides)

**Step 2: Documents**
- `FileUploader` component (drag + drop)
- Accepted: PDF, DOCX, TXT, max 50MB each
- Shows upload progress per file
- After upload: shows classified doc type + confidence badge
- Can upload multiple; list shows all uploaded

**Step 3: Review + Launch**
- Summary: company name, document count by type
- "Missing documents" warnings (e.g., no bias audit detected)
- "Run Assessment" button - triggers pipeline
- Redirects to `/assessments/:id`

### Assessment Detail (`/assessments/:id`)
Three column layout on large screens; stacked on mobile.

**Top section:**
- Company name + status tag (`InlineLoading` when processing)
- Overall score (large number) + risk tier badge (color-coded)
- "Download Report" button (if complete)
- Last updated timestamp

**Score Card panel:**
- `@carbon/charts-react` RadarChart with 8 dimensions
- Each dimension shows score (0-100) + color

**Dimension Breakdown panel:**
- `Accordion` per dimension; each shows:
  - Score bar + numeric score
  - Flags list (severity-colored tags)
  - Key findings (from extraction)

**Flags panel:**
- Filterable by severity: critical, warning, info
- Each flag: severity tag + text + source dimension

**Evidence Trail panel:**
- Grouped by document; for each finding: document name, quote
- Link to view document (presigned URL)

**External Signals panel:**
- Litigation, regulatory actions, media sentiment
- Each with severity + source + date

**Documents panel:**
- List of all uploaded documents with type badge + processing status

### Team Management (`/team`) - org_manager only
- `DataTable` of team members: name, email, role, joined date, status
- "Invite Underwriter" button opens modal with email input
- Row actions: deactivate user, revoke access

### Settings (`/settings`)
Two tabs:
- **Profile**: name, email, change password form
- **Organization** (manager only): org name, slug (readonly), industry, AI system count

### Billing Page (`/billing`) - org_manager only

**Current Plan card:**
- Tier name + description
- Assessments this month: X / Y (progress bar)
- Cost this month: $X,XXX (based on tier pricing)
- Next billing date

**Plan comparison table:**
- Shows all 4 tiers with features
- Current tier highlighted
- "Upgrade" / "Downgrade" buttons (schedules change for next month; sends email to Camille team)
- Demo orgs show "Demo Account - Contact team to upgrade"

**Usage History:**
- Monthly breakdown table: assessments run, estimated cost

---

## Backend Changes Required

### New: Organization Tier Fields
```python
# app/models/organization.py additions
tier: Mapped[str] = mapped_column(String(20), nullable=False, default="tier_1")
is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```
Migration: `004_add_org_tier.py`

### New: Password Reset Token
```python
# app/models/password_reset.py
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: UUID
    email: str (index)
    code_hash: str  # bcrypt hash of 6-digit code
    expires_at: datetime  # 15 minutes
    used_at: datetime | None
    created_at: datetime
```
Migration: `004_add_org_tier.py` (same migration)

### New: Email Service
```python
# app/services/email_service.py
# Gmail SMTP via smtplib + app password
# GMAIL_ADDRESS + GMAIL_APP_PASSWORD in config
async def send_password_reset_code(to_email: str, code: str) -> None: ...
async def send_invitation_email(to_email: str, token: str, role: str, org_name: str | None) -> None: ...
```

### New: Auth Endpoints
- `POST /api/v1/auth/password-reset/request` - generate code, store hash, send email
- `POST /api/v1/auth/password-reset/confirm` - verify code, set new password
- `GET /api/v1/auth/invitation-info` - returns role + org name for a token (no auth needed)
- `POST /api/v1/auth/signup` - accepts token + user data + optional org data; creates user (+org if manager)

### Updated: Organization Schema
Add `tier` and `is_demo` to `OrganizationResponse` and `OrganizationCreate`.

### New: Usage Endpoint
- `GET /api/v1/organizations/{org_id}/usage` - returns assessment count this month, limit for tier, estimated cost

---

## Implementation Phases

### Phase UI-1: Foundation + Auth (this phase)
**Backend:**
- PasswordResetToken model + email service
- Migration 004 (org tier fields + password reset table)
- Password reset endpoints
- Invitation info endpoint + signup endpoint
- Tests

**Frontend:**
- Scaffold (Vite + Carbon + Router + TanStack Query)
- API client (Axios + JWT interceptors)
- Auth context (token storage, login, logout)
- Protected Route component
- Login page
- Password reset request + confirm pages
- Signup (invitation accept) page
- App shell with public/protected routing

### Phase UI-2: Admin Console
**Backend:** Usage endpoint; tier field on org CRUD

**Frontend:**
- Left-nav shell with Carbon `SideNav`
- Admin dashboard + org list
- Admin invite org manager

### Phase UI-3: Assessment Workflow
**Frontend:**
- Assessment list (with tabs, filters)
- New assessment wizard (3 steps)
- Assessment detail page (score card, flags, evidence, signals)

### Phase UI-4: Team + Settings + Billing
**Frontend:**
- Team management (invite underwriter, deactivate)
- Settings pages (profile + org)
- Billing page (usage, plan comparison, upgrade/downgrade)

### Phase UI-5: Polish
- Real-time polling (3s for in-progress assessments)
- Toast notifications (Carbon `ToastNotification`)
- Loading skeletons
- Empty states
- Error boundaries

---

## File Structure

```
frontend/
├── src/
│   ├── main.tsx                  # Entry; React root; QueryClientProvider
│   ├── App.tsx                   # Router setup; auth guard
│   ├── api/
│   │   ├── client.ts             # Axios instance + interceptors
│   │   ├── auth.ts               # Auth API calls
│   │   ├── assessments.ts        # Assessment API calls
│   │   ├── organizations.ts      # Org API calls
│   │   └── types.ts              # All TypeScript types (mirrors Pydantic schemas)
│   ├── contexts/
│   │   └── AuthContext.tsx       # JWT state; login/logout; current user
│   ├── components/
│   │   ├── ProtectedRoute.tsx    # Role-aware route guard
│   │   ├── AppShell.tsx          # SideNav + Header layout wrapper
│   │   ├── RiskTierBadge.tsx     # Colored tag for low/medium/high/critical
│   │   ├── ScoreRadar.tsx        # Carbon radar chart for 8 dimensions
│   │   ├── FlagsList.tsx         # Filterable severity-tagged flags
│   │   ├── EvidenceTrail.tsx     # Document evidence citations
│   │   └── ProcessingStatus.tsx  # Inline progress for pipeline steps
│   └── pages/
│       ├── auth/
│       │   ├── Login.tsx
│       │   ├── ResetPasswordRequest.tsx
│       │   ├── ResetPasswordConfirm.tsx
│       │   └── Signup.tsx
│       ├── admin/
│       │   ├── AdminDashboard.tsx
│       │   ├── OrganizationList.tsx
│       │   └── InviteOrgManager.tsx
│       ├── assessments/
│       │   ├── AssessmentList.tsx
│       │   ├── NewAssessment.tsx
│       │   └── AssessmentDetail.tsx
│       ├── Dashboard.tsx         # Role-aware dashboard
│       ├── Team.tsx
│       ├── Settings.tsx
│       └── Billing.tsx
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

---

## Carbon Theme

Use Carbon's `g10` (light) theme - appropriate for professional insurance tools.
Apply via `<Theme theme="g10">` wrapper at root.

Color conventions:
- Critical risk: `$support-error` (red)
- High risk: `$support-warning` (orange)
- Medium risk: `$support-caution-major` (yellow)
- Low risk: `$support-success` (green)
- In Progress: `$interactive` (blue)

---

_Last updated: 2026-04-05_
