import type { RoleCode, ControlStatus, RAGStatus } from '../types';

// ─────────────────────────────────────────────────────────────
// PAGE ACCESS CONFIG  ← single source of truth for all RBAC
// Update this object to change any role's page visibility.
// Frontend (sidebar, route guards) and backend both derive from this.
// ─────────────────────────────────────────────────────────────
export const PAGE_ACCESS: Record<RoleCode, string[]> = {
  SYSTEM_ADMIN:  ['dashboard', 'data-control', 'approvals', 'evidence', 'variance', 'scorecard', 'kri-wizard', 'kri-config', 'admin', 'escalation-metrics'],
  L1_APPROVER:   ['dashboard', 'data-control', 'approvals', 'evidence'],
  L2_APPROVER:   ['dashboard', 'data-control', 'approvals', 'evidence'],
  L3_ADMIN:      ['dashboard', 'data-control', 'approvals', 'evidence', 'kri-config'],
  MANAGEMENT:    ['dashboard', 'data-control', 'scorecard', 'escalation-metrics', 'kri-config'],
  DATA_PROVIDER: ['dashboard', 'data-control', 'kri-config'],
  METRIC_OWNER:  ['dashboard', 'data-control', 'kri-config'],
};

/**
 * Returns all roles that have access to a given page.
 * Used by App.tsx route guards — change PAGE_ACCESS above, guards update automatically.
 */
export function getRolesForPage(page: string): RoleCode[] {
  return (Object.entries(PAGE_ACCESS) as [RoleCode, string[]][])
    .filter(([, pages]) => pages.includes(page))
    .map(([role]) => role);
}

/**
 * Returns all pages accessible to a given set of user roles (union).
 * Replaces the old switch-case getNavSectionsForRole.
 */
export function getAllowedPages(roles: { role_code: string }[]): string[] {
  const pages = new Set<string>();
  roles.forEach(r => {
    const allowed = PAGE_ACCESS[r.role_code as RoleCode] ?? [];
    allowed.forEach(p => pages.add(p));
  });
  return Array.from(pages);
}

// ─── Status → Color + Icon + Label (WCAG AA compliant) ─────
export const statusConfig: Record<string, { color: string; bg: string; icon: string; label: string }> = {
  // Control statuses
  COMPLETED: { color: '#1e8449', bg: '#e8f8f0', icon: '✓', label: 'SLA Met' },
  SLA_MET:   { color: '#1e8449', bg: '#e8f8f0', icon: '✓', label: 'SLA Met' },
  APPROVED:  { color: '#1e8449', bg: '#e8f8f0', icon: '✓', label: 'Approved' },
  SLA_BREACHED: { color: '#922b21', bg: '#fdecea', icon: '✕', label: 'SLA Breached' },
  NOT_STARTED:  { color: '#7f8c8d', bg: '#f0f0f0', icon: '—', label: 'Not Started' },
  PENDING_APPROVAL: { color: '#b7950b', bg: '#fef9e7', icon: '⏳', label: 'Pending' },
  IN_PROGRESS: { color: '#2471a3', bg: '#ebf5fb', icon: '▶', label: 'In Progress' },
  REWORK:      { color: '#a04000', bg: '#fbeee6', icon: '↺', label: 'Rework' },
  // Management simplified view
  PASS: { color: '#1e8449', bg: '#e8f8f0', icon: '✓', label: 'Pass' },
  FAIL: { color: '#922b21', bg: '#fdecea', icon: '✕', label: 'Fail' },
  // Approval workflow / scorecard statuses
  DRAFT:      { color: '#1565c0', bg: '#e3f2fd', icon: '✎', label: 'Draft' },
  REJECTED:   { color: '#c62828', bg: '#ffebee', icon: '✕', label: 'Rejected' },
  L1_PENDING: { color: '#f57c00', bg: '#fff8e1', icon: '⏳', label: 'L1 Pending' },
  L2_PENDING: { color: '#e65100', bg: '#fff3e0', icon: '⏳', label: 'L2 Pending' },
  L3_PENDING: { color: '#c62828', bg: '#ffebee', icon: '⏳', label: 'L3 Pending' },
  // KRI config statuses
  ACTIVE:     { color: '#1565c0', bg: '#e3f2fd', icon: '●', label: 'Active' },
  // User / rule active state (display strings, not codes)
  Active:     { color: '#1e8449', bg: '#e8f8f0', icon: '●', label: 'Active' },
  Inactive:   { color: '#7f8c8d', bg: '#f0f0f0', icon: '●', label: 'Inactive' },
};

export const ragConfig: Record<string, { color: string; bg: string; icon: string; label: string }> = {
  GREEN: { color: '#1e8449', bg: '#e8f8f0', icon: '●', label: 'Green' },
  AMBER: { color: '#b7950b', bg: '#fef9e7', icon: '●', label: 'Amber' },
  RED: { color: '#922b21', bg: '#fdecea', icon: '●', label: 'Red' },
};

export const riskConfig: Record<string, { color: string; bg: string }> = {
  LOW: { color: '#1e8449', bg: '#e8f8f0' },
  MEDIUM: { color: '#b7950b', bg: '#fef9e7' },
  HIGH: { color: '#a04000', bg: '#fbeee6' },
  CRITICAL: { color: '#922b21', bg: '#fdecea' },
};

// ─── Role → Landing page ───────────────────────────────────
// Must point to a page the role actually has access to (per PAGE_ACCESS above).
export const roleLandingPage: Record<RoleCode, string> = {
  SYSTEM_ADMIN:  '/admin',
  L3_ADMIN:      '/approvals',
  L2_APPROVER:   '/approvals',
  L1_APPROVER:   '/approvals',
  MANAGEMENT:    '/dashboard',
  DATA_PROVIDER: '/dashboard',
  METRIC_OWNER:  '/dashboard',
};

export const roleLabel: Record<RoleCode, string> = {
  MANAGEMENT: 'Management',
  L1_APPROVER: 'L1 Approver',
  L2_APPROVER: 'L2 Approver',
  L3_ADMIN: 'L3 Approver',
  DATA_PROVIDER: 'Data Provider',
  METRIC_OWNER: 'Metric Owner',
  SYSTEM_ADMIN: 'System Admin',
};

// ─── Role Permission Matrix ─────────────────────────────────
// Kept for backwards compatibility — delegates to getAllowedPages (which reads PAGE_ACCESS).
export function getNavSectionsForRole(roles: { role_code: string }[]): string[] {
  return getAllowedPages(roles);
}

export function isPrimaryRole(roles: { role_code: string }[], targetRole: RoleCode): boolean {
  return roles.some(r => r.role_code === targetRole);
}

export function getFirstAvailableLandingPage(roles: { role_code: string }[]): string {
  if (!roles || roles.length === 0) return '/dashboard';
  
  // Prioritize roles in order of hierarchy for landing page
  const roleOrder: RoleCode[] = ['SYSTEM_ADMIN', 'L3_ADMIN', 'L2_APPROVER', 'L1_APPROVER', 'MANAGEMENT', 'METRIC_OWNER', 'DATA_PROVIDER'];
  
  for (const role of roleOrder) {
    if (roles.some(r => r.role_code === role)) {
      return roleLandingPage[role];
    }
  }
  
  return '/dashboard';
}

// ─── Month helpers ──────────────────────────────────────────
export const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatPeriod(year: number, month: number): string {
  return `${monthNames[month - 1]} ${year}`;
}

export function getAvailablePeriods(count: number = 12): { year: number; month: number; label: string }[] {
  const now = new Date();
  const periods = [];
  for (let i = 0; i < count; i++) {
    let m = now.getMonth() + 1 - i;
    let y = now.getFullYear();
    while (m <= 0) { m += 12; y--; }
    periods.push({ year: y, month: m, label: formatPeriod(y, m) });
  }
  return periods;
}

// ─── Role Checking Helpers ──────────────────────────────────
/**
 * Check if user has any of the required roles
 * Usage: hasRole(user.roles, ['L1_APPROVER', 'L2_APPROVER'])
 */
export function hasRole(roles: { role_code: string }[], required: string[]): boolean {
  return roles.some(r => required.includes(r.role_code));
}

/**
 * Check if user has ALL required roles
 * Usage: hasAllRoles(user.roles, ['MANAGEMENT', 'SYSTEM_ADMIN'])
 */
export function hasAllRoles(roles: { role_code: string }[], required: string[]): boolean {
  const userRoles = new Set(roles.map(r => r.role_code));
  return required.every(r => userRoles.has(r));
}

/**
 * Check if user is a specific single role (primary role)
 * Usage: isRole(user.roles, 'SYSTEM_ADMIN')
 */
export function isRole(roles: { role_code: string }[], role: string): boolean {
  return roles.some(r => r.role_code === role);
}

/**
 * Check if user is an approver (L1, L2, L3, or SYSTEM_ADMIN)
 */
export function isApprover(roles: { role_code: string }[]): boolean {
  return hasRole(roles, ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']);
}

/**
 * Check if user is admin (SYSTEM_ADMIN or L3_ADMIN)
 */
export function isAdmin(roles: { role_code: string }[]): boolean {
  return hasRole(roles, ['SYSTEM_ADMIN', 'L3_ADMIN']);
}

/**
 * Check if user is L3 admin (can escalate and see all approvals)
 */
export function isL3Admin(roles: { role_code: string }[]): boolean {
  return hasRole(roles, ['SYSTEM_ADMIN', 'L3_ADMIN']);
}

/**
 * Check if user is data provider (can upload evidence)
 */
export function isDataProvider(roles: { role_code: string }[]): boolean {
  return hasRole(roles, ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'DATA_PROVIDER', 'SYSTEM_ADMIN']);
}

/**
 * Check if user can access system admin features (SYSTEM_ADMIN only)
 */
export function isSystemAdmin(roles: { role_code: string }[]): boolean {
  return hasRole(roles, ['SYSTEM_ADMIN']);
}
