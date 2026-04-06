# BIC-CCD Architecture Overview

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                   │
│   Browser (Desktop/Tablet)  ─── HTTPS ──→  Nginx / Ingress      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                      FRONTEND (React 18)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Dashboard │ │Data Ctrl │ │Approvals │ │ Evidence │   + 4 more│
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ Design System: Theme tokens, StatusBadge, KpiCard,  │        │
│  │ FilterBar, ChartCard — reusable across all pages    │        │
│  └─────────────────────────────────────────────────────┘        │
│  State: Redux Toolkit (UI) + TanStack React Query (server)      │
│  Build: Vite 5 + TypeScript (strict)                             │
└──────────────────────────────┬───────────────────────────────────┘
                               │ REST API (JSON)
┌──────────────────────────────▼───────────────────────────────────┐
│                      BACKEND (FastAPI)                             │
│  ┌────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐        │
│  │ Router │→│ Service  │→│ Repository │→│   ORM    │        │
│  └────────┘  └──────────┘  └────────────┘  └──────────┘        │
│  Middleware: JWT Auth → Role Check → Audit Log → Request ID      │
│  15 API routers, 53 endpoints, Pydantic V2 schemas               │
└──────────────────────────────┬───────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────▼──────┐  ┌─────────▼──────┐  ┌─────────▼──────┐
│  Oracle 19c    │  │  S3 Storage    │  │  SMTP Relay    │
│  20+ tables    │  │  Evidence      │  │  Notifications │
│  Audit columns │  │  Versioned     │  │  Escalations   │
└────────────────┘  └────────────────┘  └────────────────┘
```

## Layer Responsibilities

### Router Layer (`app/routers/`)
- HTTP request/response handling
- Input validation via Pydantic schemas
- Route-level role authorization via dependency injection
- No business logic

### Service Layer (`app/services/`)
- Business logic orchestration
- Multi-repository coordination (e.g., maker-checker involves status, audit, notification repos)
- Workflow enforcement (L1→L2→L3 approval chain)
- SLA calculation and escalation triggers

### Repository Layer (`app/repositories/`)
- Database queries via SQLAlchemy ORM
- Pagination, filtering, sorting
- No business logic — pure data access
- Reusable across services

### Middleware (`app/middleware/`)
- JWT token validation
- Role-based access control (7 roles enforced)
- Audit logging (every POST/PUT/PATCH/DELETE)
- Request ID injection for traceability

## Data Flow: Maker-Checker Workflow

```
Maker (Data Provider)
  │ POST /api/maker-checker/submit
  ▼
Service: create submission, update status → PENDING_APPROVAL
  │ Create audit trail entry
  │ Send notification to L1 approver
  ▼
L1 Approver
  │ POST /api/maker-checker/{id}/action {action: "APPROVED"}
  ▼
Service: update L1 fields, forward to L2
  │ Create audit trail entry
  │ Send notification to L2 approver
  ▼
L2 Approver → L3 Admin → COMPLETED
  │ Each level: audit trail + notification + status update
  ▼
Monthly Control Status → COMPLETED, sla_met = true/false
```

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Transport | HTTPS via nginx/ingress TLS termination |
| Authentication | JWT tokens (HS256, 8hr expiry) |
| Authorization | Role-based (7 roles), enforced at API + UI |
| Audit | Every state change logged with timestamp, SOEID, IP |
| Data | All user identities from database, zero hardcoded |
| Secrets | Environment variables, never committed to repo |

## Performance Considerations

- **Backend**: SQLAlchemy connection pooling (min 5, max 25 in prod)
- **Backend**: Paginated responses for all list endpoints
- **Frontend**: TanStack React Query with 30s stale time, background refetch
- **Frontend**: Redux Toolkit for UI state only (minimal re-renders)
- **Frontend**: Vite code splitting per page route (lazy loading)
- **Database**: Indexes on all FK columns and frequently filtered fields
- **Database**: Composite unique constraints prevent duplicate monthly records
