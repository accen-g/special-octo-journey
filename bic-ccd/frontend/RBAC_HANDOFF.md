# Role-Based Access Control (RBAC) Implementation - Handoff Document

**Date:** April 4, 2026  
**Project:** BIC-CCD (B&I Data Metrics & Controls)  
**Status:** Phase 1 Complete - Frontend Navigation Filtering Done  
**Next Phase:** Backend Analysis & Integration (in backend workspace)

---

## 📋 Executive Summary

Frontend role-based access control is **partially implemented**:
- ✅ Navigation filtering based on user roles
- ✅ Smart landing page redirects
- ✅ Role hierarchy defined
- ❌ Page-level content guards (not yet implemented)
- ❌ Backend RBAC validation (needs analysis)

**Current Workspace:** Frontend only (`bic-ccd/frontend`)  
**Next Workspace:** Backend + Frontend (`bic-ccd-project-2/bic-ccd`)

---

## 🎯 Role Definition & Requirements

### Role Hierarchy & Landing Pages

| Role Code | Display Name | Landing Page | Visible Nav Sections |
|-----------|--------------|--------------|----------------------|
| MANAGEMENT | Management | `/dashboard` | Dashboard, Scorecard, Evidence |
| L1_APPROVER | L1 Approver | `/data-control` | Data Control, Evidence, Approvals |
| L2_APPROVER | L2 Approver | `/approvals` | Approvals, Evidence, Variance |
| L3_ADMIN | L3 Approver | `/approvals` | Approvals, Evidence, Variance |
| DATA_PROVIDER | Data Provider | `/evidence` | Evidence (upload only) |
| METRIC_OWNER | Metric Owner | `/variance` | Variance, Evidence |
| SYSTEM_ADMIN | System Admin | `/admin` | ALL (Dashboard, Data Control, Approvals, Evidence, Variance, Scorecard, Admin, KRI Wizard) |

### Critical Distinction: Two L3 Sub-types

1. **L3_ADMIN** (L3 Approver Authority)
   - Can access: Approvals, Evidence, Variance pages
   - Functions: Approve/reject submissions, escalate (L3 only), view breach analytics
   - Cannot access: Admin panel, KRI Wizard, user management

2. **SYSTEM_ADMIN** (L3 Admin with full system control)
   - Can access: ALL pages + all features
   - Functions: All L3_ADMIN functions + user management, audit logs, KRI onboarding, system configuration
   - Admin-only pages: `/admin`, `/kri-wizard`

---

## ✅ What Was Implemented (Frontend)

### 1. Updated Files

#### `src/utils/helpers.ts`
**New Functions Added:**

```typescript
// Returns allowed nav paths for a user's roles
export function getNavSectionsForRole(roles: { role_code: string }[]): string[]

// Returns the appropriate landing page for user's primary role
export function getFirstAvailableLandingPage(roles: { role_code: string }[]): string

// Checks if user has a specific role
export function isPrimaryRole(roles: { role_code: string }[], targetRole: RoleCode): boolean

// Updated role labels
export const roleLabel: Record<RoleCode, string>

// Updated landing page mapping
export const roleLandingPage: Record<RoleCode, string>
```

**Key Logic:**
- Role hierarchy for landing page selection: SYSTEM_ADMIN > L3_ADMIN > L2_APPROVER > L1_APPROVER > MANAGEMENT > METRIC_OWNER > DATA_PROVIDER
- Nav sections dynamically filtered based on all user roles (supports multi-role users)
- Uses Set to avoid duplicate nav items when user has multiple roles

#### `src/components/layout/AppLayout.tsx`
**Changes:**
- Imported `getNavSectionsForRole` helper
- Added role-based filtering logic:
  ```typescript
  const allowedNavPaths = getNavSectionsForRole(user?.roles || []);
  const filteredNavSections = navSections
    .map(section => ({
      ...section,
      items: section.items.filter(item => {
        const navPath = item.path.substring(1);
        return allowedNavPaths.includes(navPath);
      }),
    }))
    .filter(section => section.items.length > 0);
  ```
- Updated render to use `filteredNavSections` instead of static `navSections`
- Nav items now dynamically appear/disappear based on user's active role

#### `src/App.tsx`
**Changes:**
- Imported `getFirstAvailableLandingPage` helper
- Added `RoleBasedRedirect` component:
  ```typescript
  function RoleBasedRedirect() {
    const { user } = useAppSelector((s) => s.auth);
    const landingPage = user?.roles ? getFirstAvailableLandingPage(user.roles) : '/dashboard';
    return <Navigate to={landingPage} replace />;
  }
  ```
- Root path `/` now redirects to role-appropriate landing page instead of hardcoded `/dashboard`
- Fallback landing pages removed; all redirects are role-aware

---

## ❌ What Still Needs Implementation

### Phase 2: Page-Level Content Guards (Frontend)

Currently, pages are **accessible** but content is **not filtered**. Need to add:

#### Admin & KRI Wizard Pages (SYSTEM_ADMIN Only)
- Add route guards in App.tsx
- Add page-level authorization checks
- Show 403 Forbidden or redirect to dashboard if unauthorized

#### Data Control Page (L1_APPROVER Only)
- Show form/submission interface only to L1_APPROVER
- Hide from other roles
- Show "Access Denied" message if accessed by unauthorized user

#### Approvals Page (L1/L2/L3 Approvers)
- Show approve/reject buttons only to users with L1_APPROVER, L2_APPROVER, or L3_ADMIN roles
- Hide approval actions from MANAGEMENT, DATA_PROVIDER, METRIC_OWNER
- Show escalate button only for L3_ADMIN

#### Variance Page (L2/L3 Only)
- Show escalate/remediate buttons only to L2_APPROVER and L3_ADMIN
- Hide from L1_APPROVER, MANAGEMENT, DATA_PROVIDER
- Show breach analytics only to those with authority

#### Evidence Page (All Authenticated Users)
- Show upload zone to: L1_APPROVER, L2_APPROVER, L3_ADMIN, DATA_PROVIDER
- Hide upload from: MANAGEMENT, METRIC_OWNER
- Show file management tools based on role

#### Scorecard Page (MANAGEMENT & SYSTEM_ADMIN)
- Currently accessible to all
- Should be restricted to MANAGEMENT and SYSTEM_ADMIN only
- Show SLA metrics and insights dashboards

### Phase 3: Backend RBAC Analysis & Integration

**To be done in backend workspace:**

1. **Analyze Backend API Endpoints**
   - Verify each endpoint enforces role-based access control
   - Check for missing authorization middleware
   - Identify endpoints that expose unauthorized data

2. **Role Definitions Alignment**
   - Confirm backend uses same role codes as frontend
   - Verify role hierarchy matches frontend logic
   - Check database schema for role permission mappings

3. **Data Filtering at API Level**
   - Verify responses are filtered by user role
   - Check if regional data access is properly restricted
   - Ensure approval pipelines only show appropriate records

4. **Token & Session Management**
   - Verify role information is included in JWT/session tokens
   - Check token refresh mechanism preserves role data
   - Ensure no privilege escalation vulnerabilities

5. **Missing Endpoints**
   - Check if backend has endpoint to return available pages/nav items per role
   - Verify all page routes have corresponding API endpoints with role guards

---

## 🛠️ Implementation Architecture

### Decision: Client-Side Navigation Filtering + Server-Side Data Filtering

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
├─────────────────────────────────────────────────────────┤
│ • Navigation filtering: AppLayout filtered nav items    │
│ • Landing page redirect: User → appropriate page        │
│ • Page-level guards: Protect admin/restricted pages    │
│ • UI/UX: Show/hide buttons based on role              │
└──────────────────────┬──────────────────────────────────┘
                       │ Authorization Header + Token
                       ↓
┌─────────────────────────────────────────────────────────┐
│                    BACKEND (API)                         │
├─────────────────────────────────────────────────────────┤
│ • Extract role from token                              │
│ • Validate endpoint access based on role               │
│ • Filter data returned based on user roles/regions     │
│ • Audit log all actions with role info                 │
│ • Reject unauthorized requests with 403 Forbidden      │
└─────────────────────────────────────────────────────────┘
```

### Role Priority for Multi-Role Users

When a user has multiple roles:
1. Navigation shows union of all accessible pages
2. Landing page uses highest-priority role (SYSTEM_ADMIN > L3_ADMIN > L2 > L1 > MANAGEMENT > METRIC_OWNER > DATA_PROVIDER)
3. Role switcher allows user to select which role context to use
4. Backend should validate requested role is in user's role list

---

## 📁 Current Folder Structure (Frontend)

```
src/
├── App.tsx (MODIFIED - Added RoleBasedRedirect)
├── main.tsx
├── api/
│   └── client.ts
├── components/
│   └── layout/
│       └── AppLayout.tsx (MODIFIED - Added role-based nav filtering)
├── hooks/
├── pages/
│   ├── Admin/
│   ├── Approvals/
│   ├── Dashboard/
│   ├── DataControl/
│   ├── Evidence/
│   ├── KriWizard/
│   ├── Login/
│   ├── Scorecard/
│   └── Variance/
├── store/
│   └── index.ts
├── types/
│   └── index.ts (Role types: RoleCode enum)
└── utils/
    ├── helpers.ts (MODIFIED - Added RBAC functions)
    └── theme.ts
```

---

## 🚀 Next Steps for Backend Workspace Chat

1. **Add backend folder to workspace**
   - Include backend API code (Node/Python/etc.)
   - Include database schema/migrations
   - Include authentication/token generation code

2. **Analyze Backend RBAC Implementation**
   - Review middleware/interceptors for role checks
   - Check API endpoint authorization
   - Verify role data is in tokens

3. **Identify Gaps & Issues**
   - Missing authorization guards
   - Data exposure vulnerabilities
   - Inconsistent role definitions

4. **Create Comprehensive RBAC Solution**
   - Backend: Add missing middleware/guards
   - Frontend: Add page-level guards
   - Ensure end-to-end role-based access control

5. **Testing Checklist**
   - Each role can only access assigned pages
   - Each role only sees appropriate data
   - Role escalation/downgrade works correctly
   - Multi-role users can switch roles properly
   - Admin-only functions are protected

---

## 📊 Testing Scenarios (For When Working Fullstack)

### Scenario 1: Management User
- ✅ Sees: Dashboard, Scorecard, Evidence in sidebar
- ❌ Doesn't see: Data Control, Approvals, Variance, Admin, KRI Wizard
- 📍 Lands on: Dashboard
- 🔒 Cannot access: `/data-control`, `/approvals`, `/admin`

### Scenario 2: L1 Approver (Maker)
- ✅ Sees: Data Control, Evidence, Approvals in sidebar
- ❌ Doesn't see: Dashboard, Variance, Admin, KRI Wizard
- 📍 Lands on: Data Control (form for new submission)
- 🔒 Cannot access: `/variance`, `/admin`, `/scorecard`

### Scenario 3: L3 Admin (System Admin)
- ✅ Sees: ALL nav items (Dashboard, Data Control, Approvals, Evidence, Variance, Scorecard, Admin, KRI Wizard)
- 📍 Lands on: Admin
- 🔓 Can access: All pages + admin functions

### Scenario 4: Multi-Role User (MANAGEMENT + L2_APPROVER)
- ✅ Sees: Dashboard, Scorecard, Evidence (MANAGEMENT) + Approvals, Variance (L2_APPROVER)
- 📍 Lands on: Dashboard (highest priority)
- Can switch between MANAGEMENT and L2_APPROVER roles using top bar chips

---

## 📞 Questions for Backend Team/Owner

When analyzing backend:

1. **Role Storage:** Where are roles stored? Database? JWT token? Both?
2. **Role Hierarchy:** Does backend have explicit role priority/hierarchy?
3. **Multi-Role Support:** Can a user have multiple roles? How is it handled?
4. **Data Filtering:** Are API responses filtered by user region + role?
5. **Admin Panel:** Already exists? How is it protected?
6. **KRI Wizard:** Already exists? Is it SYSTEM_ADMIN only?
7. **Audit Logging:** Does backend log actions with role information?
8. **Token Format:** What's the JWT/session token structure? Does it include roles?

---

## 📝 Files to Review in Backend Workspace

- Authentication service (JWT generation, role inclusion)
- API middleware/interceptors (authorization checks)
- Database schema (users, roles, user_roles table structure)
- Role-based routes/endpoints (if they exist)
- Data access layer (filtering logic)
- Audit logging system

---

## 🎓 Key Concepts for Backend Analysis

- **Frontend filtering** ≠ **security** (just UX)
- **Backend must enforce** all role-based access control
- **Never trust client-side** authorization decisions
- **Always validate** role from token/session, never from client input
- **Filter all responses** by user role + region at API level
- **Log all actions** with actor role for audit trail

---

**End of Handoff Document**

When ready to continue with backend analysis, start new chat in backend workspace and share this document for context.
