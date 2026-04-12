export type RoleCode = 'MANAGEMENT' | 'L1_APPROVER' | 'L2_APPROVER' | 'L3_ADMIN' | 'DATA_PROVIDER' | 'METRIC_OWNER' | 'SYSTEM_ADMIN';
export type ControlStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'PENDING_APPROVAL' | 'APPROVED' | 'REWORK' | 'SLA_BREACHED' | 'COMPLETED';
export type RAGStatus = 'GREEN' | 'AMBER' | 'RED';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface UserRole { role_code: RoleCode; region_id: number | null; }
export interface CurrentUser { user_id: number; soe_id: string; full_name: string; email: string; roles: UserRole[]; }
export interface AuthState { user: CurrentUser | null; token: string | null; isAuthenticated: boolean; }
export interface Region { region_id: number; region_code: string; region_name: string; }
export interface Category { category_id: number; category_code: string; category_name: string; }
export interface Dimension { dimension_id: number; dimension_code: string; dimension_name: string; display_order: number; }

export interface KRI {
  kri_id: number; kri_code: string; kri_name: string; description?: string;
  category_id: number; category_name?: string; region_id: number; region_name?: string;
  risk_level: RiskLevel; framework?: string; is_active: boolean; onboarded_dt?: string; created_dt: string;
}

export interface MonthlyStatus {
  status_id: number; kri_id: number; kri_code?: string; kri_name?: string;
  dimension_id: number; dimension_name?: string; period_year: number; period_month: number;
  status: ControlStatus; rag_status?: RAGStatus; sla_due_dt?: string; sla_met?: boolean;
  approval_level?: string; region_name?: string; category_name?: string;
}

export interface DashboardSummary {
  total_kris: number; sla_met: number; sla_met_pct: number;
  sla_breached: number; sla_breached_pct: number;
  not_started: number; not_started_pct: number;
  pending_approvals: number; regions: string[]; period: string; last_updated?: string;
}

export interface TrendDataPoint { period: string; sla_met: number; sla_breached: number; not_started: number; }
export interface DimensionBreakdown { dimension_name: string; sla_met: number; breached: number; not_started: number; }
export interface Evidence { evidence_id: number; kri_id: number; file_name: string; file_type?: string; version_number: number; is_locked: boolean; uploaded_dt: string; kri_name?: string; }
export interface MakerCheckerSubmission { submission_id: number; status_id: number; final_status: string; submitted_by: number; submitted_dt: string; l1_approver_id?: number; l1_action?: string; l2_approver_id?: number; l2_action?: string; l3_approver_id?: number; l3_action?: string; }
export interface ApprovalAudit { audit_id: number; action: string; performed_by: number; performed_dt: string; comments?: string; previous_status?: string; new_status?: string; performer_name?: string; }
export interface VarianceSubmission { variance_id: number; metric_id: number; variance_pct: number; commentary: string; review_status: string; submitted_dt: string; }
export interface Notification { notification_id: number; title: string; message: string; notification_type?: string; is_read: boolean; created_dt: string; }
export interface PaginatedResponse<T> { items: T[]; total: number; page: number; page_size: number; }
export interface EscalationConfig { config_id: number; escalation_type: string; threshold_hours: number; reminder_hours: number; escalate_to_role: string; }
export interface Comment { comment_id: number; comment_text: string; comment_type: string; posted_dt: string; poster_name?: string; }

// ─── KRI Onboarding (Bluesheet) ─────────────────────────────
export interface KriConfigListItem {
  kri_id: number; kri_code?: string; kri_name: string; description?: string;
  region_name?: string; category_name?: string; risk_level: string; frequency?: string;
  data_provider_name?: string; metric_owner_name?: string; remediation_owner_name?: string;
  version?: string; approval_status: string; submitted_by_name?: string; submitted_dt?: string;
  bluesheet_id?: number;
}

export interface KriBluesheetCreate {
  kri_code: string; kri_name: string; description?: string; legacy_kri_id?: string;
  region_id: number; category_id: number; risk_level: string; threshold?: string;
  circuit_breaker?: string; frequency: string; dq_objectives?: string; control_ids?: string;
  primary_senior_manager?: string; metric_owner_name?: string; remediation_owner_name?: string;
  bi_metrics_lead?: string; data_provider_name?: string;
  sc_uk: boolean; sc_finance: boolean; sc_risk: boolean; sc_liquidity: boolean;
  sc_capital: boolean; sc_risk_reports: boolean; sc_markets: boolean;
  why_selected?: string; threshold_rationale?: string; limitations?: string; kri_calculation?: string;
  runbook_version?: string; runbook_review_date?: string; runbook_notes?: string;
}

export interface KriBluesheetDetail extends KriBluesheetCreate {
  bluesheet_id: number; kri_id: number; kri_code?: string; kri_name: string;
  region_name?: string; category_name?: string;
  runbook_s3_path?: string; runbook_filename?: string;
  approval_status: string; submitted_by?: number; submitted_dt?: string; submitter_name?: string;
  created_dt?: string; approval_log?: KriApprovalLogEntry[];
}

export interface KriApprovalLogEntry {
  log_id: number; kri_id: number; action: string;
  performed_by: number; performer_name?: string; performed_dt: string;
  comments?: string; previous_status?: string; new_status?: string;
}

// ─── Audit Evidence ──────────────────────────────────────────
export interface AuditEvidenceItem {
  evidence_id: number;
  kri_id: number;
  kri_code?: string;
  kri_name?: string;
  control_id?: string;
  region_code?: string;
  period_year: number;
  period_month: number;
  iteration?: number;
  evidence_type: 'manual' | 'auto' | 'email';
  action?: string;
  sender?: string;
  receiver?: string;
  file_name: string;
  s3_object_path: string;
  uploaded_by_name?: string;
  notes?: string;
  is_unmapped: boolean;
  email_uuid?: string;
  created_dt?: string;
}

export interface AuditEvidenceKriRow {
  kri_id: number;
  kri_code?: string;
  kri_name: string;
  region_name?: string;
  region_code?: string;
  dimension_id: number;       // FK to CCB_KRI_CONTROL — unique per control row
  control_id?: string;        // dimension_code e.g. "TIMELINESS"
  control_name?: string;      // dimension_name e.g. "Timeliness"
  data_provider_name?: string;
  status: string;
  evidence_count: number;
  period_year: number;
  period_month: number;
}

export interface AuditSummary {
  summary_id: number;
  kri_id: number;
  period_year: number;
  period_month: number;
  s3_path: string;
  generated_dt?: string;
  l3_approver_name?: string;
  final_status: string;
  total_iterations: number;
  total_evidences: number;
  total_emails: number;
}
