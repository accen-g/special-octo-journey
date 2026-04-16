# BIC-CCD — Engineering Handover

> **Audience:** Any engineer picking this project up cold.  
> **Verified against:** Actual source files in `backend/` and `frontend/` — not README claims.  
> **Last updated:** 2026-04-12

---

## Table of Contents

1. [What Was Built / Changed (Session History)](#1-what-was-built--changed-session-history)
2. [Real Project Structure](#2-real-project-structure)
3. [Complete API Endpoint Reference](#3-complete-api-endpoint-reference)
4. [Dual Evidence System (System A vs System B)](#4-dual-evidence-system-system-a-vs-system-b)
5. [Audit Evidence System (System B) Internals](#5-audit-evidence-system-system-b-internals)
6. [KRI Onboarding / Bluesheet Workflow](#6-kri-onboarding--bluesheet-workflow)
7. [Scorecard System](#7-scorecard-system)
8. [Maker-Checker Workflow](#8-maker-checker-workflow)
9. [L3 Admin Utilities](#9-l3-admin-utilities)
10. [APScheduler Background Jobs (4 jobs)](#10-apscheduler-background-jobs-4-jobs)
11. [Escalation & Assignment Systems](#11-escalation--assignment-systems)
12. [Complete Database Table Reference (38 tables)](#12-complete-database-table-reference-38-tables)
13. [Complete Environment Variable Reference](#13-complete-environment-variable-reference)
14. [Frontend Pages — Full List (13 pages)](#14-frontend-pages--full-list-13-pages)
15. [Data Control Page — Architecture Notes](#15-data-control-page--architecture-notes)
16. [Pending Work](#16-pending-work)

---

## 1. What Was Built / Changed (Session History)

### Session 1 — Data Control Interface Modernization

**Database Schema & Migration Strategy**
- Deprecated `schema.sql` (archived to `schema.sql.legacy`). All schema changes now managed via Alembic migrations using ORM models.
- Added nullable `TRACKER_ID` FK to `CCB_KRI_EVIDENCE` (referencing `CCB_KRI_CONTROL_STATUS_TRACKER`). Implemented idempotent Alembic backfill.
- Centralized categorical definitions to `backend/app/enums.py` — connects FastAPI Pydantic schemas with Oracle `CHECK` constraints (`ENABLE NOVALIDATE` for zero downtime).

**Escalation & Workflow Bugs Fixed**
- Fixed `MakerCheckerService` routing: when L3 escalates a KRI it now resolves the dynamic "Pending With" user rather than a hardcoded static route.
- Clean 422 error handlers for edge cases.
- Standardized escalation audit payload — every routing change now injects an `"ESCALATED"` explicit enum state.
- Enforced mandatory comments via frontend validation for all Maker-Checker actions (Approve, Reject, Rework, Escalate).

**Approvals Queue UI Refactoring (`ApprovalsPage.tsx`)**
- Reduced table width from 11 to 9 columns (removed redundant SLA and Pending With columns).
- Replaced verbose text buttons with compact Icon Buttons (`CheckCircle`, `Replay`, `Cancel`, `ArrowForward`) with MUI tooltips.
- Fixed expanding row bug where inline audit trail `colSpan` was misaligned.

**Data Control Heatmap Redesign (`DataControlPage.tsx`)**
- Built custom dimension-spanning KRI tracking matrix (KRIs vs regions across all status states).
- Shifted from "pill" status badges to Data Heatmap UI — statuses dynamically tint `TableCell` background.

### Session 2 — Audit Evidence KRI × Control Refactoring

**Problem:** The Evidence page showed one row per KRI with aggregated controls. Control ID column showed "—" for all rows.

**Root cause:** `BIC_KRI_BLUESHEET.CONTROL_IDS` is always empty. The real source of truth is `KRI_CONFIGURATION` → `CCB_KRI_CONTROL.DIMENSION_CODE`.

**Changes made:**

| File | What changed |
|---|---|
| `backend/app/schemas/__init__.py` | Added `dimension_id`, `control_id`, `control_name` to `AuditEvidenceKriRow` |
| `backend/app/routers/audit_evidence.py` | `list_kris_with_evidence` rewritten to query KRI × Control configs; `upload_evidence` accepts `dimension_id` form field; `list_evidence` accepts `control_code` filter |
| `frontend/src/types/index.ts` | `AuditEvidenceKriRow` extended with `dimension_id`, `control_id`, `control_name` |
| `frontend/src/pages/Evidence/EvidencePage.tsx` | Table row key changed to `kri_id-dimension_id`; Control column shows name + code; upload passes `dimension_id`; evidence view filtered by `control_code` |

**Result:** One row per KRI × Control dimension. Each row has independent status, evidence count, upload, and view capability.

---

## 2. Real Project Structure

### Backend

```
backend/
  app/
    main.py                    ← FastAPI app, lifespan (DB init + seeding + scheduler), router inclusion
    config.py                  ← All env vars via pydantic-settings (Settings class)
    database.py                ← SQLAlchemy engine + SessionLocal + get_db dependency
    auth.py                    ← JWT creation + get_current_user dependency
    scheduler.py               ← APScheduler setup + 4 job wrappers + manual trigger functions
    middleware.py              ← RequestIdMiddleware + AuditLogMiddleware
    models/__init__.py         ← ALL SQLAlchemy ORM models (38 tables)
    schemas/__init__.py        ← ALL Pydantic request/response models
    routers/
      __init__.py              ← 18 APIRouter objects (auth, lookups, dashboard, kris, kri-config,
                                  controls, maker-checker, evidence, variance, users, escalation,
                                  escalation-metrics, notifications, comments, data-sources,
                                  admin, assignment-rules, health)
      scorecard.py             ← scorecard_router  →  /api/scorecard
      kri_onboarding.py        ← router            →  /api/kri-onboarding
      audit_evidence.py        ← router            →  /api/audit-evidence
    services/
      verification.py          ← monthly_init, daily_timeliness_check, dcrm_processing
      email.py                 ← run_daily_notifications, send helpers
    cache.py                   ← In-process TTL cache helpers
    enums.py                   ← Centralized categorical definitions (ControlStatus, RoleCode, etc.)
```

**Key point:** Almost all routers are defined in `routers/__init__.py`. Only `scorecard.py`, `kri_onboarding.py`, and `audit_evidence.py` are separate files.

### Frontend

```
frontend/src/
  App.tsx                      ← BrowserRouter + all Route definitions
  main.tsx                     ← Vite entry point, QueryClient, AuthProvider
  pages/
    Dashboard/DashboardPage.tsx
    DataControl/DataControlPage.tsx
    Approvals/ApprovalsPage.tsx
    Evidence/EvidencePage.tsx
    Variance/VariancePage.tsx
    Scorecard/ScorecardPage.tsx
    EscalationMetrics/EscalationMetricsPage.tsx
    Admin/AdminPage.tsx
    KriWizard/KriWizardPage.tsx
    KriConfig/KriConfigPage.tsx
    KriConfig/KriDetailPage.tsx
    KriConfig/KriOnboardingWizard.tsx
    Login/LoginPage.tsx
  api/                         ← Axios API client functions (one per domain)
  types/index.ts               ← All TypeScript interfaces
  contexts/                    ← AuthContext
  hooks/                       ← Custom React hooks
  store/                       ← Redux Toolkit slices
  components/                  ← Shared UI components
```

---

## 3. Complete API Endpoint Reference

**21 routers, ~95 endpoints** (README claims 15 routers / 53 endpoints — both wrong).

### Auth — `/api/auth`
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Username/password → JWT |
| GET | `/api/auth/me` | Current user profile + roles |

### Lookups — `/api/lookups`
| Method | Path | Description |
|---|---|---|
| GET | `/api/lookups/regions` | All regions |
| GET | `/api/lookups/categories` | All KRI categories |
| GET | `/api/lookups/dimensions` | All control dimensions |
| GET | `/api/lookups/statuses` | All status lookup values |

### Dashboard — `/api/dashboard`
| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/summary` | Headline stats (total KRIs, SLA met %, breached %) |
| GET | `/api/dashboard/trend` | Monthly trend data |
| GET | `/api/dashboard/dimension-breakdown` | Per-dimension SLA breakdown |
| GET | `/api/dashboard/sla-distribution` | SLA distribution chart data |
| GET | `/api/dashboard/evidence-completeness` | Evidence completeness by region |

### KRI Management — `/api/kris`
| Method | Path | Description |
|---|---|---|
| GET | `/api/kris` | List KRIs (paginated, filterable by region/category/search) |
| GET | `/api/kris/{kri_id}` | Single KRI detail |
| POST | `/api/kris` | Create KRI (SYSTEM_ADMIN) |
| PUT | `/api/kris/{kri_id}` | Update KRI (SYSTEM_ADMIN) |
| POST | `/api/kris/onboard` | Onboard KRI (creates master + configuration rows) |

### KRI Configuration — `/api/kri-config`
| Method | Path | Description |
|---|---|---|
| GET | `/api/kri-config/{kri_id}` | Get KRI × Dimension configs |
| POST | `/api/kri-config` | Create a KRI config entry |

### Data Controls — `/api/controls`
| Method | Path | Description |
|---|---|---|
| GET | `/api/controls` | List control statuses (year/month/region/dimension/status filters) |
| GET | `/api/controls/{status_id}` | Single control status detail |
| GET | `/api/controls/{status_id}/audit-trail` | Full audit trail for a control |

### Maker-Checker — `/api/maker-checker`
| Method | Path | Description |
|---|---|---|
| POST | `/api/maker-checker/submit` | Submit control for approval |
| GET | `/api/maker-checker/pending` | My pending approvals queue |
| GET | `/api/maker-checker/queue-summary` | Summary counts by approval level |
| GET | `/api/maker-checker/all-pending` | All pending (L3_ADMIN view) |
| GET | `/api/maker-checker/history` | Historical submissions |
| POST | `/api/maker-checker/{submission_id}/action` | Approve / Reject / Rework / Escalate |
| GET | `/api/maker-checker/{submission_id}` | Submission detail + audit trail |

### Evidence System A — `/api/evidence`
| Method | Path | Description |
|---|---|---|
| GET | `/api/evidence` | List evidence files (kri_id, year, month filters) |
| POST | `/api/evidence/upload` | Upload evidence file |
| POST | `/api/evidence/{evidence_id}/submit` | Submit evidence (triggers maker-checker) |
| GET | `/api/evidence/{evidence_id}/download` | Download / presigned URL |
| POST | `/api/evidence/{evidence_id}/lock` | Lock file (SYSTEM_ADMIN) |

### Variance — `/api/variance`
| Method | Path | Description |
|---|---|---|
| POST | `/api/variance/submit` | Submit variance commentary |
| GET | `/api/variance/pending` | Pending variance reviews |
| POST | `/api/variance/{variance_id}/review` | Approve / reject variance |

### Users — `/api/users`
| Method | Path | Description |
|---|---|---|
| GET | `/api/users` | List users (paginated) |
| POST | `/api/users` | Create user |
| PUT | `/api/users/{user_id}` | Update user |
| POST | `/api/users/assign-role` | Assign role to user |
| GET | `/api/users/{user_id}/roles` | Get user's role mappings |
| GET | `/api/users/by-role/{role_code}` | Users with a given role (+ optional region filter) |

### Escalation Config — `/api/escalation`
| Method | Path | Description |
|---|---|---|
| GET | `/api/escalation` | List escalation configs |
| POST | `/api/escalation` | Create escalation config |
| PUT | `/api/escalation/{config_id}` | Update threshold / reminder hours |
| DELETE | `/api/escalation/{config_id}` | Delete config |

### Escalation Metrics — `/api/escalation-metrics`
| Method | Path | Description |
|---|---|---|
| GET | `/api/escalation-metrics/summary` | SLA breach summary with overdue hours |

### Notifications — `/api/notifications`
| Method | Path | Description |
|---|---|---|
| GET | `/api/notifications` | List notifications (unread_only filter) |
| GET | `/api/notifications/count` | Unread count |
| POST | `/api/notifications/{id}/read` | Mark as read |

### Comments — `/api/comments`
| Method | Path | Description |
|---|---|---|
| POST | `/api/comments` | Add comment to a KRI/submission |
| GET | `/api/comments/kri/{kri_id}` | Comments for a KRI |

### Data Sources — `/api/data-sources`
| Method | Path | Description |
|---|---|---|
| GET | `/api/data-sources/{kri_id}` | Data source mappings for a KRI |
| POST | `/api/data-sources` | Create data source mapping |

### L3 Admin — `/api/admin`
| Method | Path | Description |
|---|---|---|
| POST | `/api/admin/controls/{status_id}/override` | Override control status (L3_ADMIN bypass) |
| GET | `/api/admin/controls/{status_id}/audit-trail` | Admin audit trail view |
| POST | `/api/admin/scheduler/monthly-init` | Manually trigger monthly init |
| POST | `/api/admin/scheduler/timeliness-check` | Manually trigger timeliness check |
| POST | `/api/admin/scheduler/dcrm-processing` | Manually trigger DCRM processing |
| POST | `/api/admin/cache/refresh` | Invalidate all caches |
| GET | `/api/admin/cache/stats` | Cache hit/miss stats |
| POST | `/api/admin/sql/query` | Execute read-only SQL (L3_ADMIN) |

### Assignment Rules — `/api/assignment-rules`
| Method | Path | Description |
|---|---|---|
| GET | `/api/assignment-rules` | List approval assignment rules |
| POST | `/api/assignment-rules` | Create rule |
| PUT | `/api/assignment-rules/{rule_id}` | Update rule |
| DELETE | `/api/assignment-rules/{rule_id}` | Delete rule |

### Scorecard — `/api/scorecard`
| Method | Path | Description |
|---|---|---|
| GET | `/api/scorecard` | List scorecards (year/month/region filters) |
| GET | `/api/scorecard/{scorecard_id}` | Scorecard detail |
| POST | `/api/scorecard` | Create scorecard |
| POST | `/api/scorecard/{scorecard_id}/submit` | Submit for approval |
| POST | `/api/scorecard/{scorecard_id}/approve` | Approve scorecard |
| POST | `/api/scorecard/{scorecard_id}/reject` | Reject scorecard |

### KRI Onboarding — `/api/kri-onboarding`
| Method | Path | Description |
|---|---|---|
| GET | `/api/kri-onboarding` | List all bluesheets |
| GET | `/api/kri-onboarding/{kri_id}` | Bluesheet detail |
| POST | `/api/kri-onboarding` | Submit full bluesheet (creates KRI + bluesheet) |
| POST | `/api/kri-onboarding/draft` | Save as draft |
| PATCH | `/api/kri-onboarding/{kri_id}/draft` | Update draft fields |
| POST | `/api/kri-onboarding/{kri_id}/resubmit` | Resubmit after rejection |
| POST | `/api/kri-onboarding/{kri_id}/runbook` | Upload runbook PDF |
| POST | `/api/kri-onboarding/{kri_id}/approve` | Approve / reject bluesheet |

### Audit Evidence System B — `/api/audit-evidence`
| Method | Path | Description |
|---|---|---|
| GET | `/api/audit-evidence/kris` | KRI × Control rows (one per combination) with status + evidence count |
| GET | `/api/audit-evidence` | List evidence metadata (kri_id / year / month / control_code filters) |
| POST | `/api/audit-evidence/upload` | Upload evidence (multipart; includes `dimension_id` form field) |
| GET | `/api/audit-evidence/{kri_id}/presigned-url/{evidence_id}` | S3 presigned download URL |
| POST | `/api/audit-evidence/email/outbound` | Send outbound email (creates `.eml` in S3) |
| POST | `/api/audit-evidence/email/inbound` | Ingest inbound email as evidence |
| GET | `/api/audit-evidence/{kri_id}/summary` | Audit summary for a KRI/period |
| POST | `/api/audit-evidence/{kri_id}/generate-summary` | Trigger L3 summary generation |
| GET | `/api/audit-evidence/local-download` | Dev-mode local file download (DEV_MOCK_S3=true) |
| GET | `/api/audit-evidence/dev/email-log` | Dev-mode: view mock email log |
| DELETE | `/api/audit-evidence/dev/email-log` | Dev-mode: clear mock email log |

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness (returns `{"status": "ok"}`) |
| GET | `/api/health` | DB ping health check |

---

## 4. Dual Evidence System (System A vs System B)

Two separate, parallel evidence systems exist. This is the most confusing architectural aspect.

| | System A | System B |
|---|---|---|
| **Purpose** | Operational evidence in maker-checker workflow | Audit evidence for L3 / external auditor review |
| **DB table** | `CCB_KRI_EVIDENCE` | `BIC_KRI_EVIDENCE_METADATA` |
| **ORM model** | `EvidenceMetadata` | `KriEvidenceMetadata` |
| **Router** | `routers/__init__.py` → `/api/evidence` | `routers/audit_evidence.py` → `/api/audit-evidence` |
| **S3 prefix** | `BIC/KRI/…` (set by `EVIDENCE_S3_BASE_PATH`) | `BIC/KRI/{region}/{year}/{month}/Evidences/…` |
| **Granularity** | Per KRI × period | Per KRI × Control (dimension) × period |
| **Control link** | `evidence.status_id` → `CCB_KRI_CONTROL_STATUS_TRACKER` | `metadata.control_id` = `dimension_code` string |
| **Used by page** | Submission/workflow screens | `/evidence` Evidence page |

---

## 5. Audit Evidence System (System B) Internals

### S3 path structure

```
BIC/KRI/{region_code}/{year}/{month:02d}/Evidences/TEMP/{dimension_code}/COMMON/{timestamp}_{filename}
```

Example:
```
BIC/KRI/APAC/2025/06/Evidences/TEMP/DATA_PROVIDER_SLA/COMMON/20250612_153042_report.xlsx
```

`TEMP` → `FINAL` once the L3 summary is generated.

### Control dimension codes (seeded in dev)

| Code | Name |
|---|---|
| `DATA_PROVIDER_SLA` | Data Provider SLA |
| `COMPLETENESS_ACCURACY` | Completeness & Accuracy |
| `MATERIAL_PREPARER` | Material Preparer |
| `VARIANCE_ANALYSIS` | Variance Analysis |
| `REVIEWS` | Reviews |
| `ADJ_TRACKING` | Adjustments Tracking |
| `CHANGE_GOVERNANCE` | Change Governance |

### Email trail

When an email is ingested via `POST /api/audit-evidence/email/inbound`:
1. Raw `.eml` written to S3 with `evidence_type = 'email'`
2. Row inserted/updated in `BIC_KRI_EMAIL_ITERATION` (iteration counter per KRI × period)
3. `email_uuid` stored in `BIC_KRI_EVIDENCE_METADATA` to de-duplicate re-ingested emails
4. `sender` and `receiver` parsed from headers and stored

### Local dev without S3

Set `DEV_MOCK_S3=true`. All S3 ops replaced with local filesystem under `./local_evidence_store/`. Path structure preserved. Use `GET /api/audit-evidence/local-download?key=…` to serve these files.

Set `DEV_MOCK_EMAIL=true` to write email payloads to disk (`./dev_emails/`) instead of calling `EMAIL_SERVICE_URL`.

---

## 6. KRI Onboarding / Bluesheet Workflow

Allows new KRIs to be proposed, configured, and approved before entering the operational monitoring cycle.

### Tables

| Table | Purpose |
|---|---|
| `BIC_KRI_BLUESHEET` | All bluesheet form fields (threshold, circuit breaker, frequency, DQ objectives, scope checkboxes, etc.) |
| `BIC_KRI_APPROVAL_LOG` | Audit log of every action on a bluesheet |

### Approval states

```
DRAFT → SUBMITTED → APPROVED
                 ↘ REJECTED → (edit → resubmit → SUBMITTED)
```

### Key fields in `BIC_KRI_BLUESHEET`

- `threshold`, `circuit_breaker`, `frequency`, `dq_objectives`, `control_ids`
- `primary_senior_manager`, `metric_owner_name`, `remediation_owner_name`, `bi_metrics_lead`, `data_provider_name`
- Scope booleans: `sc_uk`, `sc_finance`, `sc_risk`, `sc_liquidity`, `sc_capital`, `sc_risk_reports`, `sc_markets`
- `why_selected`, `threshold_rationale`, `limitations`, `kri_calculation`
- `runbook_version`, `runbook_review_date`, `runbook_notes`, `runbook_s3_path`, `runbook_filename`

### Runbook upload

`POST /api/kri-onboarding/{kri_id}/runbook` uploads PDF to S3. Path stored in `BIC_KRI_BLUESHEET.RUNBOOK_S3_PATH`.

### Frontend

Routes: `/kri-config` (list), `/kri-config/new` (wizard), `/kri-config/:kriId` (detail)  
Components: `KriConfigPage.tsx`, `KriOnboardingWizard.tsx`, `KriDetailPage.tsx`

---

## 7. Scorecard System

The Scorecard system has its **own dedicated tables** and router (`scorecard.py`). It does NOT reuse `MAKER_CHECKER_SUBMISSION`.

### Tables

| Table | Purpose |
|---|---|
| `CCB_SCORECARD` | Scorecard records (region × year × month, status, summary data) |
| `CCB_SCORECARD_APPROVER` | Who is assigned to approve a scorecard |
| `CCB_SCORECARD_ACTIVITY_LOG` | Activity log for each scorecard action |

### Approval states

```
DRAFT → SUBMITTED → APPROVED
                 ↘ REJECTED → (edit → resubmit)
```

### `_is_scorecard` helper

`scorecard.py` has an internal `_is_scorecard(sub)` function that checks `submission_notes` for a `"SCORECARD:"` prefix — this is a legacy check for older records stored in `MAKER_CHECKER_SUBMISSION` before the dedicated table was added. New records always use `CCB_SCORECARD`.

### Frontend

Route: `/scorecard` → `ScorecardPage.tsx`

---

## 8. Maker-Checker Workflow

### Table: `MAKER_CHECKER_SUBMISSION`

Tracks the L1 → L2 → L3 approval chain for control-level submissions.

| Column | Meaning |
|---|---|
| `status_id` | FK to `CCB_KRI_CONTROL_STATUS_TRACKER` |
| `submitted_by` | FK to `APP_USER` |
| `l1_approver_id`, `l1_action`, `l1_action_dt` | L1 review outcome |
| `l2_approver_id`, `l2_action`, `l2_action_dt` | L2 review outcome |
| `l3_approver_id`, `l3_action`, `l3_action_dt` | L3 review outcome |
| `final_status` | `L1_PENDING` / `L2_PENDING` / `L3_PENDING` / `APPROVED` / `REJECTED` / `REWORK` |

### Table: `APPROVAL_AUDIT_TRAIL`

Per-action log: `SUBMITTED`, `L1_APPROVED`, `L2_APPROVED`, `L3_APPROVED`, `REJECTED`, `REWORK`, `ESCALATED`, `L3_OVERRIDE`.

### Actions available via `POST /api/maker-checker/{submission_id}/action`

- `APPROVE` — moves to next level or marks APPROVED at L3
- `REJECT` — terminal rejection
- `REWORK` — sends back to data provider
- `ESCALATE` — routes to next level, inserting `ESCALATED` audit entry
- **All actions require a non-empty `comments` field** (enforced frontend + backend)

### L3 Admin Override

`POST /api/admin/controls/{status_id}/override` bypasses the full chain. Logged as `L3_OVERRIDE` in `APPROVAL_AUDIT_TRAIL`.

---

## 9. L3 Admin Utilities

Accessible only to roles: `L3_ADMIN`, `SYSTEM_ADMIN`.

### Read-only SQL console

`POST /api/admin/sql/query` with body `{"query": "SELECT …"}`

- Only SELECT statements allowed (enforced server-side; non-SELECT raises 403)
- Returns rows as JSON
- **Risk:** gives direct read access to any table — ensure DB user grants are scoped in production

### Cache management

- `GET /api/admin/cache/stats` — hit/miss/size per named cache
- `POST /api/admin/cache/refresh` — invalidate all TTL caches

**Multi-worker note:** Each gunicorn worker has its own in-process cache. Cache refresh only clears the worker that handles the request. Restart workers or call multiple times to clear all workers. Redis is not yet implemented.

### Scheduler manual triggers

- `POST /api/admin/scheduler/monthly-init` — run monthly init now
- `POST /api/admin/scheduler/timeliness-check` — run timeliness check now
- `POST /api/admin/scheduler/dcrm-processing` — run DCRM processing now

---

## 10. APScheduler Background Jobs (4 jobs)

Defined in `backend/app/scheduler.py`. Run in-process via `AsyncIOScheduler`. All use ShedLock-pattern distributed locking via `CCB_SHED_LOCK` table.

### Job 1 — `monthly_init`
**Schedule:** 1st of every month at 01:00 UTC (`CronTrigger(day=1, hour=1, minute=0)`)  
**Grace:** 1 hour (tolerate late startup)  
**What it does:** `app.services.verification.monthly_init(db, year, month)` — creates `CCB_KRI_CONTROL_STATUS_TRACKER` skeleton rows for every active KRI × dimension for the new period.

### Job 2 — `daily_timeliness_check`
**Schedule:** Mon–Fri at 08:00 UTC  
**What it does:** `app.services.verification.daily_timeliness_check(db)` — finds overdue controls and flips status to `SLA_BREACHED`.

### Job 3 — `dcrm_processing`
**Schedule:** Mon–Fri at 08:30 UTC  
**What it does:** `app.services.verification.dcrm_processing(db)` — processes DCRM BD2/BD3/BD8 deadlines.

### Job 4 — `daily_notifications`
**Schedule:** Mon–Fri at 07:30 UTC (before timeliness check)  
**What it does:** `app.services.email.run_daily_notifications(db)` — sends SLA reminder and escalation emails.

### ShedLock mechanism

```
Table: CCB_SHED_LOCK
Columns: job_name, lock_until, locked_at, locked_by

Before job: SELECT ... WITH FOR UPDATE SKIP LOCKED
  - If no row → INSERT with lock_until = now + 5min
  - If lock_until <= now → UPDATE (steal lock)
  - If lock_until > now → skip job

After job: UPDATE SET lock_until = now - 1s  (release)
```

Lock TTL = 300 seconds (5 min). If a process dies mid-job, another instance steals the lock after 5 minutes.

---

## 11. Escalation & Assignment Systems

### Escalation Config (`ESCALATION_CONFIG` table)

| Column | Meaning |
|---|---|
| `escalation_type` | e.g. `'SLA_BREACH'`, `'PENDING_APPROVAL'` |
| `threshold_hours` | Hours after deadline before escalating |
| `reminder_hours` | Hours between reminder emails |
| `escalate_to_role` | Role that receives escalation |

Managed via `/api/escalation` CRUD. Frontend: `EscalationMetricsPage.tsx` at `/escalation-metrics`.

### Assignment Rules (`APPROVAL_ASSIGNMENT_RULE` table)

Determines which user fulfils which approval role for a given KRI/region.

| Column | Meaning |
|---|---|
| `kri_id` | Nullable — if NULL, applies to all KRIs in region |
| `region_id` | Nullable — if NULL, applies globally |
| `role_code` | `L1_APPROVER` / `L2_APPROVER` / `L3_ADMIN` |
| `assigned_user_id` | FK to `APP_USER` |

**Resolution order (most specific wins):**
1. `kri_id = X AND region_id = R`
2. `kri_id = X AND region_id IS NULL`
3. `kri_id IS NULL AND region_id = R`
4. `kri_id IS NULL AND region_id IS NULL` (global default)

Managed via `/api/assignment-rules` CRUD. Also accessible from `AdminPage.tsx`.

---

## 12. Complete Database Table Reference (38 tables)

All actual table names verified from `backend/app/models/__init__.py`.

### CCB_ prefix tables (workflow / control engine)

| Table | ORM Model | Purpose |
|---|---|---|
| `CCB_REGION` | `RegionMaster` | Region master |
| `CCB_KRI_CATEGORY` | `KriCategoryMaster` | Category lookup |
| `CCB_KRI_CONTROL` | `ControlDimensionMaster` | Control dimension master (7 dimensions) |
| `CCB_KRI_STATUS` | `KriStatusLookup` | Status name lookup |
| `CCB_KRI_CONFIG` | `KriMaster` | KRI master definitions |
| `CCB_KRI_METRIC` | `MetricValues` | Per-KRI × dimension × period metric values |
| `CCB_KRI_COMMENT` | `KriComment` | Comments on KRIs |
| `CCB_KRI_CONTROL_STATUS_TRACKER` | `MonthlyControlStatus` | Per-KRI × control × year × month status |
| `CCB_KRI_CONTROL_EVIDENCE_AUDIT` | `EvidenceVersionAudit` | Evidence version audit log |
| `CCB_KRI_EVIDENCE` | `EvidenceMetadata` | System A evidence files |
| `CCB_KRI_USER_ROLE` | `KriUserRole` | KRI-level user role overrides |
| `CCB_ROLE_REGION_MAPPING` | `RoleRegionMapping` | Role ↔ region access mappings |
| `CCB_KRI_DATA_SOURCE_MAPPING` | `DataSourceMapping` | Data source definitions per KRI |
| `CCB_KRI_DATA_SOURCE_STATUS_TRACKER` | `DataSourceStatusTracker` | Data source receipt tracking |
| `CCB_KRI_ASSIGNMENT_TRACKER` | `KriAssignment` | KRI user assignments |
| `CCB_KRI_ASSIGNMENT_AUDIT` | `AssignmentAudit` | Assignment change audit log |
| `CCB_SCORECARD` | `ScorecardCase` | Scorecard records |
| `CCB_SCORECARD_APPROVER` | `ScorecardApprover` | Scorecard approval assignments |
| `CCB_SCORECARD_ACTIVITY_LOG` | `ScorecardActivityLog` | Scorecard action log |
| `CCB_CASE` | `BicCase` | Generic case tracker |
| `CCB_CASE_FILE` | `CaseFile` | Files attached to cases |
| `CCB_EMAIL_AUDIT` | `EmailAudit` | Email send audit log |
| `CCB_SHED_LOCK` | `SchedulerLock` | Distributed scheduler locks |

### Non-prefixed tables (cross-cutting)

| Table | ORM Model | Purpose |
|---|---|---|
| `APP_USER` | `AppUser` | User accounts (soe_id, email, full_name, department) |
| `USER_ROLE_MAPPING` | `UserRoleMapping` | User ↔ role ↔ region assignments |
| `KRI_CONFIGURATION` | `KriConfiguration` | KRI × Control dimension links (is_active, sla_days, etc.) |
| `MAKER_CHECKER_SUBMISSION` | `MakerCheckerSubmission` | Approval chain records (L1/L2/L3) |
| `APPROVAL_AUDIT_TRAIL` | `ApprovalAuditTrail` | Per-action audit log |
| `VARIANCE_SUBMISSION` | `VarianceSubmission` | Variance commentary records |
| `ESCALATION_CONFIG` | `EscalationConfig` | Escalation threshold configuration |
| `NOTIFICATION` | `Notification` | Per-user notifications |
| `APPROVAL_ASSIGNMENT_RULE` | `ApprovalAssignmentRule` | Who approves what for which KRI/region |
| `SAVED_VIEW` | `SavedView` | User-saved filter/view preferences |

### BIC_ prefix tables (KRI operational / audit)

| Table | ORM Model | Purpose |
|---|---|---|
| `BIC_KRI_BLUESHEET` | `KriBluesheet` | Onboarding bluesheet form data |
| `BIC_KRI_APPROVAL_LOG` | `KriApprovalLog` | Bluesheet approval actions |
| `BIC_KRI_EVIDENCE_METADATA` | `KriEvidenceMetadata` | System B audit evidence records |
| `BIC_KRI_EMAIL_ITERATION` | `KriEmailIteration` | Email ingestion iteration counters |
| `BIC_KRI_AUDIT_SUMMARY` | `KriAuditSummary` | L3-generated audit summaries |

### Key relationships

```
CCB_KRI_CONFIG (kri_id)
  ↓  KRI_CONFIGURATION (kri_id + dimension_id)  ←  CCB_KRI_CONTROL (dimension_id)
  ↓  CCB_KRI_CONTROL_STATUS_TRACKER (kri_id + dimension_id + year + month)
       ↓  MAKER_CHECKER_SUBMISSION (status_id)
            ↓  APPROVAL_AUDIT_TRAIL (submission_id)
  ↓  BIC_KRI_EVIDENCE_METADATA (kri_id + control_id [dimension_code] + year + month)
  ↓  CCB_KRI_EVIDENCE (kri_id + status_id)
  ↓  BIC_KRI_BLUESHEET (kri_id)
       ↓  BIC_KRI_APPROVAL_LOG (kri_id)
```

---

## 13. Complete Environment Variable Reference

Verified from `backend/app/config.py` (pydantic-settings `Settings` class).

### Application

| Variable | Default | Notes |
|---|---|---|
| `APP_NAME` | `BIC-CCD` | Application name |
| `APP_VERSION` | `1.0.0` | Returned by `/api/health` |
| `DEBUG` | `False` | Enable debug mode |
| `ENV` | `development` | `development` / `staging` / `production` |
| `SECRET_KEY` | `change-me-in-production` | **Must change in prod** |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed origins |

### Database (Oracle)

| Variable | Default | Notes |
|---|---|---|
| `DB_HOST` | `localhost` | Oracle DB host |
| `DB_PORT` | `1521` | Oracle listener port |
| `DB_SERVICE` | `XEPDB1` | Oracle service name |
| `DB_USER` | `bic_ccd` | DB username |
| `DB_PASSWORD` | `bic_ccd_pass` | DB password |
| `DB_POOL_MIN` | `2` | Connection pool minimum |
| `DB_POOL_MAX` | `10` | Connection pool maximum |
| `DB_POOL_INCREMENT` | `1` | Pool growth increment |

### Database (SQLite fallback — dev)

| Variable | Default | Notes |
|---|---|---|
| `USE_SQLITE` | `True` | **Set `False` for Oracle** |
| `SQLITE_URL` | `sqlite:///./bic_ccd.db` | SQLite file path |

### S3 / Object Storage

| Variable | Default | Notes |
|---|---|---|
| `S3_ENDPOINT` | `None` | Custom endpoint (MinIO / LocalStack) |
| `S3_BUCKET` | `bic-ccd-evidence` | S3 bucket name |
| `S3_ACCESS_KEY` | `` | AWS/MinIO access key |
| `S3_SECRET_KEY` | `` | AWS/MinIO secret key |
| `S3_REGION` | `us-east-1` | S3 region |
| `S3_PRESIGNED_EXPIRY` | `900` | Presigned URL TTL (seconds = 15 min) |
| `EVIDENCE_S3_BASE_PATH` | `BIC/KRI` | S3 key prefix for all evidence |
| `EVIDENCE_MAX_FILE_SIZE_MB` | `25` | Max upload file size |

### Email (HTTP service — primary)

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_SERVICE_URL` | `` | Full URL to `/mail/send` endpoint |
| `EMAIL_FROM_ADDRESS` | `` | From address |
| `EMAIL_UUID_HEADER` | `` | Custom header for email UUID tracking |
| `EMAIL_TEMPLATE_TYPE` | `BicDataMetrics` | Email template type |
| `EMAIL_TEMPLATE_NAME` | `` | Template name |
| `EMAIL_ENVIRONMENT` | `UAT` | Environment label in emails |
| `EMAIL_MODULE_NAME` | `BIC_KRI_EVIDENCE` | Module identifier in emails |

### SMTP (legacy — kept for backward compat)

| Variable | Default | Notes |
|---|---|---|
| `SMTP_HOST` | `localhost` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | `` | SMTP username |
| `SMTP_PASSWORD` | `` | SMTP password |
| `SMTP_FROM` | `bic-ccd@company.com` | From address |
| `SMTP_TLS` | `True` | Use STARTTLS |

### Dev mock switches

| Variable | Default | Notes |
|---|---|---|
| `DEV_MOCK_S3` | `False` | `True` → use `./local_evidence_store/` instead of real S3 |
| `DEV_MOCK_EMAIL` | `False` | `True` → write email payloads to `./dev_emails/` instead of HTTP call |

### Auth / JWT

| Variable | Default | Notes |
|---|---|---|
| `JWT_SECRET` | `jwt-secret-change-me` | **Must change in prod** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `480` | Token lifetime (8 hours) |

### Scheduler

| Variable | Default | Notes |
|---|---|---|
| `SCHEDULER_ENABLED` | `True` | `False` disables APScheduler entirely (use in test envs) |

---

## 14. Frontend Pages — Full List (13 pages)

Verified from `frontend/src/App.tsx`.

| Route | Component | Notes |
|---|---|---|
| `/login` | `LoginPage.tsx` | Public — JWT login form |
| `/dashboard` | `DashboardPage.tsx` | Headline stats, trend charts, dimension breakdown, evidence completeness |
| `/data-control` | `DataControlPage.tsx` | KRI × Dimension control status heatmap matrix |
| `/approvals` | `ApprovalsPage.tsx` | Maker-checker pending queue + history |
| `/evidence` | `EvidencePage.tsx` | Audit evidence — one row per KRI × Control dimension |
| `/variance` | `VariancePage.tsx` | Variance commentary submission and review |
| `/scorecard` | `ScorecardPage.tsx` | Region scorecard — submit and approve |
| `/escalation-metrics` | `EscalationMetricsPage.tsx` | SLA breach escalation tracker |
| `/admin` | `AdminPage.tsx` | Cache, SQL console, scheduler, assignment rules |
| `/kri-wizard` | `KriWizardPage.tsx` | KRI creation wizard (quick path) |
| `/kri-config` | `KriConfigPage.tsx` | KRI list + bluesheet management |
| `/kri-config/new` | `KriOnboardingWizard.tsx` | Full multi-tab bluesheet creation form |
| `/kri-config/:kriId` | `KriDetailPage.tsx` | KRI detail — bluesheet, configs, status, evidence |

### Route protection

All routes under `/` are wrapped in `ProtectedRoute` (checks `isAuthenticated` from `AuthContext`). Unauthenticated users redirect to `/login`. Role-based page visibility is controlled by `RoleBasedRedirect` on the index route.

### Roles (7 total)

`MANAGEMENT`, `L1_APPROVER`, `L2_APPROVER`, `L3_ADMIN`, `DATA_PROVIDER`, `METRIC_OWNER`, `SYSTEM_ADMIN`

---

## 15. Data Control Page — Architecture Notes

`DataControlPage.tsx` has two view modes: **Controls View** and **KRI View**.

### Controls View

- Fetches from `GET /api/controls` with region/dimension/status/year/month filters
- Uses the imported `<FilterBar regions={regions} />` component for filters
- Renders a heatmap table: KRI rows × dimension columns, cell color = control status

### KRI View

- Client-side filtering using `useMemo` — no additional API calls
- Has its own local state for `kriRegionFilter` and `kriCategoryFilter`
- These render inline dropdowns at the top of the KRI table

### Known issue (pending work)

The two views use different filter implementations — Controls View uses `<FilterBar>`, KRI View has local inline dropdowns. The user requested these to be unified into a single persistent header-level filter bar that works across both views without layout shift when toggling between them. **This work was not started.**

---

## 16. Pending Work

### High priority

**1. Unify DataControlPage filters**  
- Hoist `kriRegionFilter` / `kriCategoryFilter` state up to page level  
- Modify `<FilterBar>` (or create a new `<UnifiedFilterBar>`) to handle both Controls and KRI view filter needs from a single persistent top bar  
- No layout shift when toggling between views  
- Controls View still calls API with filter params; KRI View still does client-side `useMemo` slicing

### Completed

- [x] Control ID column fix (Control IDs now sourced from `KRI_CONFIGURATION` → `CCB_KRI_CONTROL.DIMENSION_CODE`)
- [x] Evidence page: one row per KRI × Control dimension
- [x] Independent evidence upload per control (via `dimension_id` form field)
- [x] Per-control status and evidence count in the Evidence table
- [x] Approvals Queue UI refactoring (compact icon buttons, column reduction)
- [x] Data Control Heatmap redesign (cell-background tinting)
- [x] Maker-Checker escalation dynamic routing fix
- [x] Mandatory comments enforcement for all approval actions

---

*For questions, start from `backend/app/routers/__init__.py` (main router file) and `backend/app/models/__init__.py` (all ORM models). The `backend/app/config.py` has every env var with its default.*
