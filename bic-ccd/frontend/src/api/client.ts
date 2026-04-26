import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bic_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('bic_token');
      localStorage.removeItem('bic_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;

// ─── Auth ───────────────────────────────────────────────────
export const authApi = {
  login: (soe_id: string, password: string) => api.post('/auth/login', { soe_id, password }),
  me: () => api.get('/auth/me'),
};

// ─── Lookups ────────────────────────────────────────────────
export const lookupApi = {
  regions: () => api.get('/lookups/regions'),
  categories: () => api.get('/lookups/categories'),
  dimensions: () => api.get('/lookups/dimensions'),
};

// ─── Dashboard ──────────────────────────────────────────────
export const dashboardApi = {
  summary: (params?: Record<string, unknown>) => api.get('/dashboard/summary', { params }),
  trend: (params?: Record<string, unknown>) => api.get('/dashboard/trend', { params }),
  dimensionBreakdown: (params?: Record<string, unknown>) => api.get('/dashboard/dimension-breakdown', { params }),
  slaDistribution: (params?: Record<string, unknown>) => api.get('/dashboard/sla-distribution', { params }),
  evidenceCompleteness: (params?: Record<string, unknown>) => api.get('/dashboard/evidence-completeness', { params }),
};

// ─── KRI ────────────────────────────────────────────────────
export const kriApi = {
  list: (params?: Record<string, unknown>) => api.get('/kris', { params }),
  get: (id: number) => api.get(`/kris/${id}`),
  create: (data: unknown) => api.post('/kris', data),
  update: (id: number, data: unknown) => api.put(`/kris/${id}`, data),
  onboard: (data: unknown) => api.post('/kris/onboard', data),
};

// ─── Controls ───────────────────────────────────────────────
export const controlApi = {
  list: (params?: Record<string, unknown>) => api.get('/controls', { params }),
  get: (id: number) => api.get(`/controls/${id}`),
  auditTrail: (id: number) => api.get(`/controls/${id}/audit-trail`),
};

// ─── Maker Checker ──────────────────────────────────────────
export const makerCheckerApi = {
  submit: (data: unknown) => api.post('/maker-checker/submit', data),
  pending: (params?: Record<string, unknown>) => api.get('/maker-checker/pending', { params }),
  history: (params?: Record<string, unknown>) => api.get('/maker-checker/history', { params }),
  action: (id: number, data: unknown) => api.post(`/maker-checker/${id}/action`, data),
  get: (id: number) => api.get(`/maker-checker/${id}`),
};

// ─── Evidence ───────────────────────────────────────────────
export const evidenceApi = {
  list: (params?: Record<string, unknown>) => api.get('/evidence', { params }),
  upload: (formData: FormData) => api.post('/evidence/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  lock: (id: number) => api.post(`/evidence/${id}/lock`),
};

// ─── Variance ───────────────────────────────────────────────
export const varianceApi = {
  submit: (data: unknown) => api.post('/variance/submit', data),
  pending: (params?: Record<string, unknown>) => api.get('/variance/pending', { params }),
  review: (id: number, params: Record<string, unknown>) => api.post(`/variance/${id}/review`, null, { params }),
};

// ─── Users ──────────────────────────────────────────────────
export const userApi = {
  list: (params?: Record<string, unknown>) => api.get('/users', { params }),
  create: (data: unknown) => api.post('/users', data),
  update: (id: number, data: unknown) => api.put(`/users/${id}`, data),
  assignRole: (data: unknown) => api.post('/users/assign-role', data),
  roles: (id: number) => api.get(`/users/${id}/roles`),
  byRole: (role: string, regionId?: number) => api.get(`/users/by-role/${role}`, { params: { region_id: regionId } }),
};

// ─── Escalation ─────────────────────────────────────────────
export const escalationApi = {
  list: () => api.get('/escalation'),
  create: (data: unknown) => api.post('/escalation', data),
  update: (id: number, data: unknown) => api.put(`/escalation/${id}`, data),
  remove: (id: number) => api.delete(`/escalation/${id}`),
};

// ─── Notifications ──────────────────────────────────────────
export const notificationApi = {
  list: (unreadOnly?: boolean) => api.get('/notifications', { params: { unread_only: unreadOnly } }),
  count: () => api.get('/notifications/count'),
  markRead: (id: number) => api.post(`/notifications/${id}/read`),
};

// ─── Comments ───────────────────────────────────────────────
export const commentApi = {
  add: (data: unknown) => api.post('/comments', data),
  forKri: (kriId: number) => api.get(`/comments/kri/${kriId}`),
};

// ─── Config ─────────────────────────────────────────────────
export const configApi = {
  forKri: (kriId: number) => api.get(`/kri-config/${kriId}`),
  create: (data: unknown) => api.post('/kri-config', data),
};

// ─── Data Sources ───────────────────────────────────────────
export const dataSourceApi = {
  forKri: (kriId: number) => api.get(`/data-sources/${kriId}`),
  create: (data: unknown) => api.post('/data-sources', data),
};

// ─── Approval Assignment Rules ──────────────────────────────
export const assignmentRuleApi = {
  list: () => api.get('/assignment-rules'),
  create: (data: unknown) => api.post('/assignment-rules', data),
  update: (id: number, data: unknown) => api.put(`/assignment-rules/${id}`, data),
  remove: (id: number) => api.delete(`/assignment-rules/${id}`),
};

// ─── Scorecard ──────────────────────────────────────────────
export const scorecardApi = {
  list:    (params?: Record<string, unknown>) => api.get('/scorecard', { params }),
  get:     (id: number) => api.get(`/scorecard/${id}`),
  create:  (data: unknown) => api.post('/scorecard', data),
  submit:  (id: number, notes?: string) => api.post(`/scorecard/${id}/submit`, { notes }),
  approve: (id: number, comments?: string) => api.post(`/scorecard/${id}/approve`, { comments }),
  reject:  (id: number, comments: string) => api.post(`/scorecard/${id}/reject`, { comments }),
};

// ─── KRI Onboarding (Bluesheet) ─────────────────────────────
export const kriOnboardingApi = {
  list:         (params?: Record<string, unknown>) => api.get('/kri-onboarding', { params }),
  get:          (kriId: number) => api.get(`/kri-onboarding/${kriId}`),
  submit:       (data: unknown) => api.post('/kri-onboarding', data),
  // Draft CRUD — POST creates, PATCH updates existing draft
  saveDraft:    (data: unknown) => api.post('/kri-onboarding/draft', data),
  updateDraft:  (kriId: number, data: unknown) => api.patch(`/kri-onboarding/${kriId}/draft`, data),
  uploadRunbook: (kriId: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    // Do NOT set Content-Type manually — axios sets it with the correct multipart boundary
    return api.post(`/kri-onboarding/${kriId}/runbook`, fd);
  },
  approve: (kriId: number, action: string, comments?: string) =>
    api.post(`/kri-onboarding/${kriId}/approve`, { action, comments }),
  resubmit: (kriId: number) => api.post(`/kri-onboarding/${kriId}/resubmit`),
};

// ─── Audit Evidence ─────────────────────────────────────────
export const auditEvidenceApi = {
  listKris: (params?: Record<string, unknown>) => api.get('/audit-evidence/kris', { params }),
  list: (params?: Record<string, unknown>) => api.get('/audit-evidence', { params }),
  upload: (fd: FormData) =>
    api.post('/audit-evidence/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  presignedUrl: (kriId: number, evidenceId: number) =>
    api.get(`/audit-evidence/${kriId}/presigned-url/${evidenceId}`),
  getSummary: (kriId: number, params?: { year?: number; month?: number }) =>
    api.get(`/audit-evidence/${kriId}/summary`, { params }),
  generateSummary: (kriId: number, data: { year: number; month: number; control_code?: string }) =>
    api.post(`/audit-evidence/${kriId}/generate-summary`, data),
  sendOutboundEmail: (data: {
    kri_id: number; year: number; month: number; action: string;
    recipient_emails: string[]; performed_by_user_id?: number;
  }) => api.post('/audit-evidence/email/outbound', data),
};

// ─── Admin utilities (Phase 7) ───────────────────────────────
export const adminApi = {
  cacheStats:   () => api.get('/admin/cache/stats'),
  cacheRefresh: (keys?: string[]) => api.post('/admin/cache/refresh', keys ? { keys } : {}),
  sqlQuery:     (query: string, params?: Record<string, unknown>, maxRows?: number) =>
    api.post('/admin/sql/query', { query, params, max_rows: maxRows ?? 200 }),
  // Scheduler triggers
  triggerMonthlyInit:   (year?: number, month?: number) =>
    api.post('/admin/scheduler/monthly-init', null, { params: { year, month } }),
  triggerTimeliness:    () => api.post('/admin/scheduler/timeliness-check'),
  triggerDcrm:          () => api.post('/admin/scheduler/dcrm-processing'),
};
