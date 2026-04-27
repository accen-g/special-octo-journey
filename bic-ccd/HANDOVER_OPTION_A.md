# HANDOVER — Option A: Two Fully Self-Contained Table Sets with Toggle

**Date:** 2026-04-27  
**Author:** Claude (for next session)  
**Goal:** Make CCB_* and BIC_CCD_* each 100% self-contained, with a toggle to switch between them.

---

## Background & Decision

The BIC-CCD app currently has an **incomplete** BIC_CCD_* set. The toggle (`USE_BIC_CCD_TABLES`) only switches 24 CCB_* KRI tables to their BIC_CCD_* equivalents. But 14 app-owned tables (users, approvals, variance, notifications, bluesheet, etc.) have **no BIC_CCD_* counterpart** — they still point to CCB_* FKs. This means with the toggle ON, the approval workflow is broken because `MAKER_CHECKER_SUBMISSION` still FKs to `CCB_KRI_CONTROL_STATUS_TRACKER`.

**Option A** = add BIC_CCD_* versions of all 14 missing app-owned tables, fix all FKs within each set to be self-contained, and expand the toggle to cover everything.

**Eventually (post-QA):** Option B — drop CCB_* entirely, one schema only. But for now Option A is the target.

**User will populate BIC_CCD_* tables manually. Do not auto-seed BIC_CCD_* data.**

---

## Important: Actual Oracle Table Names (NOT the Python class names)

The Python class name ≠ Oracle table name in many cases. Do NOT confuse them:

| Python Class | Oracle Table (CCB_* set) | Oracle Table (BIC_CCD_* set) |
|---|---|---|
| `RegionMaster` | `CCB_REGION` | `BIC_CCD_REGION` |
| `KriCategoryMaster` | `CCB_KRI_CATEGORY` | `BIC_CCD_KRI_CATEGORY` |
| `ControlDimensionMaster` | `CCB_KRI_CONTROL` | `BIC_CCD_KRI_CONTROL` |
| `KriStatusLookup` | `CCB_KRI_STATUS` | `BIC_CCD_KRI_STATUS` |
| `KriMaster` | `CCB_KRI_CONFIG` ← NOT KRI_MASTER | `BIC_CCD_KRI_CONFIG` ← NOT BIC_CCD_KRI_MASTER |
| `MetricValues` | `CCB_KRI_METRIC` | `BIC_CCD_KRI_METRIC` |
| `KriComment` | `CCB_KRI_COMMENT` | `BIC_CCD_KRI_COMMENT` |
| `MonthlyControlStatus` | `CCB_KRI_CONTROL_STATUS_TRACKER` | `BIC_CCD_KRI_CONTROL_STATUS_TRACKER` |
| `EvidenceVersionAudit` | `CCB_KRI_CONTROL_EVIDENCE_AUDIT` | `BIC_CCD_KRI_CONTROL_EVIDENCE_AUDIT` |
| `EvidenceMetadata` | `CCB_KRI_EVIDENCE` | `BIC_CCD_KRI_EVIDENCE` |
| `KriUserRole` | `CCB_KRI_USER_ROLE` | `BIC_CCD_KRI_USER_ROLE` |
| `RoleRegionMapping` | `CCB_ROLE_REGION_MAPPING` | `BIC_CCD_ROLE_REGION_MAPPING` |
| `DataSourceMapping` | `CCB_KRI_DATA_SOURCE_MAPPING` | `BIC_CCD_KRI_DATA_SOURCE_MAPPING` |
| `DataSourceStatusTracker` | `CCB_KRI_DATA_SOURCE_STATUS_TRACKER` | `BIC_CCD_KRI_DATA_SOURCE_STATUS_TRACKER` |
| `KriAssignment` | `CCB_KRI_ASSIGNMENT_TRACKER` | `BIC_CCD_KRI_ASSIGNMENT_TRACKER` |
| `AssignmentAudit` | `CCB_KRI_ASSIGNMENT_AUDIT` | `BIC_CCD_KRI_ASSIGNMENT_AUDIT` |
| `ScorecardCase` | `CCB_SCORECARD` | `BIC_CCD_SCORECARD` |
| `ScorecardApprover` | `CCB_SCORECARD_APPROVER` | `BIC_CCD_SCORECARD_APPROVER` |
| `ScorecardActivityLog` | `CCB_SCORECARD_ACTIVITY_LOG` | `BIC_CCD_SCORECARD_ACTIVITY_LOG` |
| `BicCase` | `CCB_CASE` | `BIC_CCD_CASE` |
| `CaseFile` | `CCB_CASE_FILE` | `BIC_CCD_CASE_FILE` |
| `EmailAudit` | `CCB_EMAIL_AUDIT` | `BIC_CCD_EMAIL_AUDIT` |
| `SchedulerLock` | `CCB_SHED_LOCK` | `BIC_CCD_SHED_LOCK` |
| `KriConfiguration` | `KRI_CONFIGURATION` | `BIC_CCD_KRI_CONFIGURATION` |

---

## Current State — What Exists vs What's Missing

### CCB_* set (`app/models/__init__.py`, uses `Base`)

**Group 1 — BIC 23 tables (CCB_* prefix):** All 23 exist, self-contained, FKs all within CCB_*.

**Group 2 — App-owned tables (no prefix):** These are the problem — they have no BIC_CCD_* equivalent yet, and their FKs point into CCB_* tables:

| Oracle Table | Python Class | Cross-set FKs (broken when toggle ON) |
|---|---|---|
| `APP_USER` | `AppUser` | None (standalone) |
| `USER_ROLE_MAPPING` | `UserRoleMapping` | → `APP_USER`, → `CCB_REGION` |
| `KRI_CONFIGURATION` | `KriConfiguration` | → `CCB_KRI_CONFIG`, → `CCB_KRI_CONTROL` |
| `MAKER_CHECKER_SUBMISSION` | `MakerCheckerSubmission` | → `CCB_KRI_CONTROL_STATUS_TRACKER` ← **PRIMARY BLOCKER**, → `CCB_KRI_EVIDENCE`, → `APP_USER` |
| `APPROVAL_AUDIT_TRAIL` | `ApprovalAuditTrail` | → `CCB_KRI_CONTROL_STATUS_TRACKER`, → `APP_USER` |
| `VARIANCE_SUBMISSION` | `VarianceSubmission` | → `CCB_KRI_METRIC`, → `CCB_KRI_CONTROL_STATUS_TRACKER`, → `APP_USER` |
| `ESCALATION_CONFIG` | `EscalationConfig` | → `CCB_REGION` |
| `NOTIFICATION` | `Notification` | → `APP_USER` |
| `APPROVAL_ASSIGNMENT_RULE` | `ApprovalAssignmentRule` | → `APP_USER`, → `CCB_REGION`, → `CCB_KRI_CONFIG`, → `CCB_KRI_CATEGORY` |
| `SAVED_VIEW` | `SavedView` | → `APP_USER` |

**Group 3 — Onboarding tables (BIC_KRI_* prefix):** Also no BIC_CCD_* equivalent yet:

| Oracle Table | Python Class | Cross-set FKs |
|---|---|---|
| `BIC_KRI_BLUESHEET` | `KriBluesheet` | → `CCB_KRI_CONFIG`, → `APP_USER` |
| `BIC_KRI_APPROVAL_LOG` | `KriApprovalLog` | → `CCB_KRI_CONFIG`, → `APP_USER` |
| `BIC_KRI_EVIDENCE_METADATA` | `KriEvidenceMetadata` | → `CCB_KRI_CONFIG`, → `APP_USER` |
| `BIC_KRI_EMAIL_ITERATION` | `KriEmailIteration` | → `CCB_KRI_CONFIG` |
| `BIC_KRI_AUDIT_SUMMARY` | `KriAuditSummary` | → `CCB_KRI_CONFIG`, → `APP_USER` |

### BIC_CCD_* set (`app/models/bic_ccd/__init__.py`, uses `BicCcdBase`)

**What already exists (24 tables):** All 23 CCB_* equivalents + `BIC_CCD_KRI_CONFIGURATION`. ✓

**Known issue in existing BIC_CCD_* models:** When `AppUser` was in `Base` (not `BicCcdBase`), cross-metadata FKs were stripped — these fields exist as bare `Integer` instead of proper `ForeignKey(...)`:

| Model | Column | Should be FK to |
|---|---|---|
| `BicCcdKriComment` | `posted_by` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdMonthlyControlStatus` | `assigned_to` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdMonthlyControlStatus` | `current_approver` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdEvidenceVersionAudit` | `assigned_to` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdEvidenceVersionAudit` | `performed_by` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdEvidenceMetadata` | `uploaded_by` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdKriUserRole` | `user_id` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdKriAssignment` | `assigned_user_id` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdAssignmentAudit` | `assigned_user_id` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdAssignmentAudit` | `assigned_by` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdScorecardCase` | `created_by_user` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdScorecardApprover` | `user_id` | `BIC_CCD_APP_USER.USER_ID` |
| `BicCcdScorecardActivityLog` | `performed_by` | `BIC_CCD_APP_USER.USER_ID` |

Also the relationships that reference AppUser are missing from BicCcd* models (they were removed when FK was stripped). Once `BIC_CCD_APP_USER` exists, these relationships must be added back.

---

## What Needs to Be Done (Exact Steps)

### Step 1 — Add 14 new BicCcd* model classes to `backend/app/models/bic_ccd/__init__.py`

Add these classes **in dependency order** (APP_USER first, because all others FK to it):

1. **`BicCcdAppUser`** → `BIC_CCD_APP_USER`  
   Copy exactly from `AppUser` (`APP_USER`) in `models/__init__.py`. Use `BicCcdBase`. No FK changes needed — this is standalone.

2. **`BicCcdUserRoleMapping`** → `BIC_CCD_USER_ROLE_MAPPING`  
   Copy from `UserRoleMapping`. Change FKs:  
   - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
   - `CCB_REGION.REGION_ID` → `BIC_CCD_REGION.REGION_ID`  
   Constraint name: `uq_bic_ccd_user_role_region`

3. **`BicCcdMakerCheckerSubmission`** → `BIC_CCD_MAKER_CHECKER_SUBMISSION`  
   Copy from `MakerCheckerSubmission`. Change FKs:  
   - `CCB_KRI_CONTROL_STATUS_TRACKER.ID` → `BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID`  
   - `CCB_KRI_EVIDENCE.ID` → `BIC_CCD_KRI_EVIDENCE.ID`  
   - All `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
   Relationships: `control_status` → `BicCcdMonthlyControlStatus`, `evidence` → `BicCcdEvidenceMetadata`, `submitter` → `BicCcdAppUser`

4. **`BicCcdApprovalAuditTrail`** → `BIC_CCD_APPROVAL_AUDIT_TRAIL`  
   Copy from `ApprovalAuditTrail`. Change FKs:  
   - `CCB_KRI_CONTROL_STATUS_TRACKER.ID` → `BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID`  
   - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
   Relationships: `performer` → `BicCcdAppUser`, `control_status` → `BicCcdMonthlyControlStatus`

5. **`BicCcdVarianceSubmission`** → `BIC_CCD_VARIANCE_SUBMISSION`  
   Copy from `VarianceSubmission`. Change FKs:  
   - `CCB_KRI_METRIC.METRIC_ID` → `BIC_CCD_KRI_METRIC.METRIC_ID`  
   - `CCB_KRI_CONTROL_STATUS_TRACKER.ID` → `BIC_CCD_KRI_CONTROL_STATUS_TRACKER.ID`  
   - All `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
   Relationship: `metric` → `BicCcdMetricValues`

6. **`BicCcdEscalationConfig`** → `BIC_CCD_ESCALATION_CONFIG`  
   Copy from `EscalationConfig`. Change FK:  
   - `CCB_REGION.REGION_ID` → `BIC_CCD_REGION.REGION_ID`

7. **`BicCcdNotification`** → `BIC_CCD_NOTIFICATION`  
   Copy from `Notification`. Change FK:  
   - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
   Relationship: `user` → `BicCcdAppUser`

8. **`BicCcdApprovalAssignmentRule`** → `BIC_CCD_APPROVAL_ASSIGNMENT_RULE`  
   Copy from `ApprovalAssignmentRule`. Change FKs:  
   - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
   - `CCB_REGION.REGION_ID` → `BIC_CCD_REGION.REGION_ID`  
   - `CCB_KRI_CONFIG.KRI_ID` → `BIC_CCD_KRI_CONFIG.KRI_ID`  
   - `CCB_KRI_CATEGORY.CATEGORY_ID` → `BIC_CCD_KRI_CATEGORY.CATEGORY_ID`  
   Index name: `idx_bic_ccd_aar_role_region`  
   Relationships: `user` → `BicCcdAppUser`, `region` → `BicCcdRegionMaster`, `kri` → `BicCcdKriMaster`, `category` → `BicCcdKriCategoryMaster`

9. **`BicCcdSavedView`** → `BIC_CCD_SAVED_VIEW`  
   Copy from `SavedView`. Change FK:  
   - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`

10. **`BicCcdKriBluesheet`** → `BIC_CCD_KRI_BLUESHEET`  
    Copy from `KriBluesheet` (`BIC_KRI_BLUESHEET`). Change FKs:  
    - `CCB_KRI_CONFIG.KRI_ID` → `BIC_CCD_KRI_CONFIG.KRI_ID`  
    - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
    Relationships: `kri` → `BicCcdKriMaster`, `submitter` → `BicCcdAppUser`

11. **`BicCcdKriApprovalLog`** → `BIC_CCD_KRI_APPROVAL_LOG`  
    Copy from `KriApprovalLog` (`BIC_KRI_APPROVAL_LOG`). Change FKs:  
    - `CCB_KRI_CONFIG.KRI_ID` → `BIC_CCD_KRI_CONFIG.KRI_ID`  
    - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
    Relationships: `kri` → `BicCcdKriMaster`, `performer` → `BicCcdAppUser`

12. **`BicCcdKriEvidenceMetadata`** → `BIC_CCD_KRI_EVIDENCE_METADATA`  
    Copy from `KriEvidenceMetadata` (`BIC_KRI_EVIDENCE_METADATA`). Change FKs:  
    - `CCB_KRI_CONFIG.KRI_ID` → `BIC_CCD_KRI_CONFIG.KRI_ID`  
    - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
    Index name: `idx_bic_ccd_evmeta_kri_period`  
    Relationships: `kri` → `BicCcdKriMaster`, `uploader` → `BicCcdAppUser`

13. **`BicCcdKriEmailIteration`** → `BIC_CCD_KRI_EMAIL_ITERATION`  
    Copy from `KriEmailIteration` (`BIC_KRI_EMAIL_ITERATION`). Change FK:  
    - `CCB_KRI_CONFIG.KRI_ID` → `BIC_CCD_KRI_CONFIG.KRI_ID`  
    Constraint name: `uq_bic_ccd_kri_iter_period`  
    Relationship: `kri` → `BicCcdKriMaster`

14. **`BicCcdKriAuditSummary`** → `BIC_CCD_KRI_AUDIT_SUMMARY`  
    Copy from `KriAuditSummary` (`BIC_KRI_AUDIT_SUMMARY`). Change FKs:  
    - `CCB_KRI_CONFIG.KRI_ID` → `BIC_CCD_KRI_CONFIG.KRI_ID`  
    - `APP_USER.USER_ID` → `BIC_CCD_APP_USER.USER_ID`  
    Relationships: `kri` → `BicCcdKriMaster`, `generator` → `BicCcdAppUser`

---

### Step 2 — Fix bare Integer fields in existing BicCcd* models (`bic_ccd/__init__.py`)

Now that `BicCcdAppUser` exists, restore proper `ForeignKey(...)` on all fields listed in the table above, and add back the `relationship(...)` where they were removed. Exact changes:

```python
# BicCcdKriComment
posted_by: Mapped[int] = mapped_column("POSTED_BY", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
poster: Mapped["BicCcdAppUser"] = relationship()

# BicCcdMonthlyControlStatus
assigned_to: Mapped[Optional[int]] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"))
current_approver: Mapped[Optional[int]] = mapped_column("CURRENT_APPROVER", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"))

# BicCcdEvidenceVersionAudit
assigned_to: Mapped[Optional[int]] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"))
performed_by: Mapped[Optional[int]] = mapped_column("PERFORMED_BY", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"))

# BicCcdEvidenceMetadata
uploaded_by: Mapped[int] = mapped_column("UPLOADED_BY", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
uploader: Mapped["BicCcdAppUser"] = relationship(foreign_keys=[uploaded_by])

# BicCcdKriUserRole
user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)

# BicCcdKriAssignment
assigned_user_id: Mapped[int] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
assigned_user: Mapped["BicCcdAppUser"] = relationship()

# BicCcdAssignmentAudit
assigned_user_id: Mapped[int] = mapped_column("ASSIGNED_TO", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
assigned_by: Mapped[int] = mapped_column("CREATED_BY_USER", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
assigned_user: Mapped["BicCcdAppUser"] = relationship(foreign_keys=[assigned_user_id])
assigned_by_user: Mapped["BicCcdAppUser"] = relationship(foreign_keys=[assigned_by])

# BicCcdScorecardCase
created_by_user: Mapped[int] = mapped_column("CREATED_BY_USER_ID", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
creator: Mapped["BicCcdAppUser"] = relationship(foreign_keys=[created_by_user])

# BicCcdScorecardApprover
user_id: Mapped[int] = mapped_column("USER_ID", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"), nullable=False)
user: Mapped["BicCcdAppUser"] = relationship(foreign_keys=[user_id])

# BicCcdScorecardActivityLog
performed_by: Mapped[Optional[int]] = mapped_column("PERFORMED_BY", Integer, ForeignKey("BIC_CCD_APP_USER.USER_ID"))
performer: Mapped[Optional["BicCcdAppUser"]] = relationship(foreign_keys=[performed_by])
```

---

### Step 3 — Add aliases at the bottom of `bic_ccd/__init__.py`

At the bottom of `bic_ccd/__init__.py`, after the existing aliases block, add:

```python
AppUser = BicCcdAppUser
UserRoleMapping = BicCcdUserRoleMapping
MakerCheckerSubmission = BicCcdMakerCheckerSubmission
ApprovalAuditTrail = BicCcdApprovalAuditTrail
VarianceSubmission = BicCcdVarianceSubmission
EscalationConfig = BicCcdEscalationConfig
Notification = BicCcdNotification
ApprovalAssignmentRule = BicCcdApprovalAssignmentRule
SavedView = BicCcdSavedView
KriBluesheet = BicCcdKriBluesheet
KriApprovalLog = BicCcdKriApprovalLog
KriEvidenceMetadata = BicCcdKriEvidenceMetadata
KriEmailIteration = BicCcdKriEmailIteration
KriAuditSummary = BicCcdKriAuditSummary
```

---

### Step 4 — Expand the toggle in `backend/app/models/__init__.py`

In the `if _get_settings().USE_BIC_CCD_TABLES:` block at the bottom of `models/__init__.py`, add the 14 new imports:

```python
if _get_settings().USE_BIC_CCD_TABLES:
    from app.models.bic_ccd import (  # noqa: F401, F811
        # existing 24...
        RegionMaster,
        KriCategoryMaster,
        ControlDimensionMaster,
        KriStatusLookup,
        KriMaster,
        MetricValues,
        KriComment,
        MonthlyControlStatus,
        EvidenceVersionAudit,
        EvidenceMetadata,
        KriUserRole,
        RoleRegionMapping,
        DataSourceMapping,
        DataSourceStatusTracker,
        KriAssignment,
        AssignmentAudit,
        ScorecardCase,
        ScorecardApprover,
        ScorecardActivityLog,
        BicCase,
        CaseFile,
        EmailAudit,
        SchedulerLock,
        KriConfiguration,
        # NEW — 14 app-owned tables
        AppUser,
        UserRoleMapping,
        MakerCheckerSubmission,
        ApprovalAuditTrail,
        VarianceSubmission,
        EscalationConfig,
        Notification,
        ApprovalAssignmentRule,
        SavedView,
        KriBluesheet,
        KriApprovalLog,
        KriEvidenceMetadata,
        KriEmailIteration,
        KriAuditSummary,
    )
```

---

### Step 5 — Update `_ccb_model_refs` and remove joinedload hack

Once Step 4 is done, the joinedload chain hack (`_CcbMonthlyControlStatus`, `_CcbKriMaster`) **can be removed** because:
- `MakerCheckerSubmission` when toggle=ON now becomes `BicCcdMakerCheckerSubmission`
- Its `control_status` FK now points to `BIC_CCD_KRI_CONTROL_STATUS_TRACKER`
- So `.joinedload(MonthlyControlStatus.kri)` resolves correctly within the same metadata

**Steps:**
1. Remove `_CcbMonthlyControlStatus = MonthlyControlStatus` and `_CcbKriMaster = KriMaster` lines from `models/__init__.py`
2. In `repositories/__init__.py`, remove the imports `_CcbMonthlyControlStatus, _CcbKriMaster`
3. In `repositories/__init__.py`, change all 3 joinedload occurrences back to use `MonthlyControlStatus` and `KriMaster` directly:
   - `joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.kri).joinedload(KriMaster.region)`
   - `joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.dimension)`
   - `joinedload(MakerCheckerSubmission.control_status).joinedload(MonthlyControlStatus.kri)`

4. Update `_ccb_model_refs` to also include the app-owned CCB-path classes (so GC doesn't collect them when toggle rebinds the names):
```python
_ccb_model_refs = [
    RegionMaster, KriCategoryMaster, ControlDimensionMaster, KriStatusLookup,
    KriMaster, MetricValues, KriComment, MonthlyControlStatus,
    EvidenceVersionAudit, EvidenceMetadata, KriUserRole, RoleRegionMapping,
    DataSourceMapping, DataSourceStatusTracker, KriAssignment, AssignmentAudit,
    ScorecardCase, ScorecardApprover, ScorecardActivityLog, BicCase,
    CaseFile, EmailAudit, SchedulerLock, KriConfiguration,
    # App-owned (now also toggled)
    AppUser, UserRoleMapping, MakerCheckerSubmission, ApprovalAuditTrail,
    VarianceSubmission, EscalationConfig, Notification, ApprovalAssignmentRule,
    SavedView, KriBluesheet, KriApprovalLog, KriEvidenceMetadata,
    KriEmailIteration, KriAuditSummary,
]
```
Note: `_ccb_model_refs` must be set **before** the `if USE_BIC_CCD_TABLES:` block, capturing the CCB_* versions.

---

### Step 6 — Update `backend/tests/conftest.py`

The conftest likely sets `USE_BIC_CCD_TABLES=true` in the test env. After Step 4, the test fixtures that create SQLite engines must call both:
```python
Base.metadata.create_all(bind=engine)       # CCB_* tables
BicCcdBase.metadata.create_all(bind=engine) # BIC_CCD_* tables (now includes APP_USER etc.)
```
This is already done for `test_verification_service.py` — verify conftest does the same.

Tests that seed `AppUser` directly must check which metadata `AppUser` resolves to when toggle is ON. With toggle ON, `AppUser` = `BicCcdAppUser` (BicCcdBase). The seeding code in conftest may need to import explicitly from the right module if it creates engine fixtures that only call one metadata's `create_all`.

---

### Step 7 — Oracle DDL (tell the user)

The user **manually creates and populates BIC_CCD_* tables**. After code changes, give the user the CREATE TABLE DDL for the 14 new tables so they can run them in Oracle. The DDL should match the model definitions exactly (column names come from the Oracle column name argument in `mapped_column()`).

---

## File Map

| File | What to change |
|---|---|
| `backend/app/models/bic_ccd/__init__.py` | Add 14 new BicCcd* classes (Step 1), fix bare Integer FKs (Step 2), add aliases (Step 3) |
| `backend/app/models/__init__.py` | Expand toggle import block (Step 4), update `_ccb_model_refs` (Step 5), remove `_CcbMonthlyControlStatus`/`_CcbKriMaster` (Step 5) |
| `backend/app/repositories/__init__.py` | Remove `_CcbMonthlyControlStatus`/`_CcbKriMaster` imports and restore clean joinedload chains (Step 5) |
| `backend/tests/conftest.py` | Verify both `Base` and `BicCcdBase` metadata tables are created (Step 6) |
| `backend/tests/test_verification_service.py` | Already has both `create_all` calls — verify still passes |

---

## Do NOT Change

- `frontend/` — no frontend changes needed for Option A
- `backend/app/services/__init__.py` — service layer already imports from `app.models` by name, toggle handles the rest
- `backend/app/routers/__init__.py` — same, no changes needed
- `backend/app/middleware/__init__.py` — no changes needed
- Seed data functions — user populates BIC_CCD_* manually; only `AppUser`/`UserRoleMapping` (CCB path) get seeded on startup

---

## Verification Checklist

After implementation:
- [ ] `USE_BIC_CCD_TABLES=false` → server starts, uses all CCB_* and un-prefixed tables as before
- [ ] `USE_BIC_CCD_TABLES=true` → server starts, all imports resolve to BIC_CCD_* tables
- [ ] `MakerCheckerSubmission.control_status` FK resolves to `BIC_CCD_KRI_CONTROL_STATUS_TRACKER` when toggle ON
- [ ] `AppUser` resolves to `BIC_CCD_APP_USER` when toggle ON (login still works)
- [ ] `pytest backend/tests/` — all tests pass (run with `USE_BIC_CCD_TABLES=true` as set in conftest)
- [ ] No SQLAlchemy relationship resolution errors on server start

---

## Key Architectural Reminder

After QA, **Option B** will follow: drop CCB_* entirely, delete the toggle, delete `_ccb_model_refs`, delete `models/bic_ccd/` module, unify everything under one `Base`. Option A is a stepping stone — don't over-engineer it.
