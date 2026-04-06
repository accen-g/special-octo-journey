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
