import React, { useState, useMemo } from 'react';
import {
  Box, Card, CardContent, Typography, Tabs, Tab, Button, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Select, MenuItem, FormControl, InputLabel,
  Collapse, IconButton, Tooltip, Pagination,
} from '@mui/material';
import {
  CheckCircle, Cancel, Replay, ArrowForward, KeyboardArrowDown,
  KeyboardArrowUp, Folder, Comment, History, FilterAlt, FilterAltOff,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { makerCheckerApi, userApi, commentApi, controlApi, lookupApi } from '../../api/client';
import { useAppSelector } from '../../store';
import { hasRole, isL3Admin, getAvailablePeriods } from '../../utils/helpers';
import TableHeaderFilters from '../../components/common/TableHeaderFilters';

// ─── Status chip helper ───────────────────────────────────────
const statusChip = (status: string) => {
  const map: Record<string, { label: string; bg: string; color: string }> = {
    L1_PENDING: { label: 'L1 Pending', bg: '#fff8e1', color: '#f57c00' },
    L2_PENDING: { label: 'L2 Pending', bg: '#fff3e0', color: '#e65100' },
    L3_PENDING: { label: 'L3 Pending', bg: '#fce4ec', color: '#c62828' },
    APPROVED:   { label: 'Approved',   bg: '#e8f5e9', color: '#2e7d32' },
    REJECTED:   { label: 'Rejected',   bg: '#ffebee', color: '#c62828' },
    REWORK:     { label: 'Rework',     bg: '#fff3e0', color: '#e65100' },
    PENDING:    { label: 'Pending',    bg: '#fff8e1', color: '#f57c00' },
  };
  const s = map[status] || { label: status, bg: '#f5f5f5', color: '#616161' };
  return (
    <Chip
      label={s.label}
      size="small"
      sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, fontSize: '0.72rem' }}
    />
  );
};

// ─── Action chip helper ──────────────────────────────────────
const actionChip = (action: string | null) => {
  if (!action) return <Typography variant="caption" sx={{ color: 'text.disabled' }}>—</Typography>;
  const map: Record<string, { bg: string; color: string }> = {
    APPROVED: { bg: '#e8f5e9', color: '#2e7d32' },
    REJECTED: { bg: '#ffebee', color: '#c62828' },
    REWORK:   { bg: '#fff3e0', color: '#e65100' },
    ESCALATE: { bg: '#f3e5f5', color: '#6a1b9a' },
  };
  const s = map[action] || { bg: '#f5f5f5', color: '#616161' };
  return (
    <Chip label={action} size="small" sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, fontSize: '0.72rem' }} />
  );
};

// ─── SLA chip helper ─────────────────────────────────────────
const slaChip = (ragStatus: string | null, slaDue: string | null) => {
  if (!ragStatus && !slaDue) return null;
  const map: Record<string, { bg: string; color: string }> = {
    GREEN: { bg: '#e8f5e9', color: '#2e7d32' },
    AMBER: { bg: '#fff8e1', color: '#f57c00' },
    RED:   { bg: '#ffebee', color: '#c62828' },
  };
  const s = map[ragStatus || ''] || { bg: '#f5f5f5', color: '#616161' };
  const label = slaDue
    ? `SLA: ${new Date(slaDue).toLocaleDateString('en-GB')}`
    : ragStatus || 'N/A';
  return (
    <Chip label={label} size="small" sx={{ bgcolor: s.bg, color: s.color, fontWeight: 600, fontSize: '0.72rem' }} />
  );
};

// ─── Inline audit trail ──────────────────────────────────────
const actionColor = (action: string) => {
  if (/APPROVED|SUBMITTED/.test(action)) return { color: '#2e7d32', bg: '#e8f5e9' };
  if (/REJECTED/.test(action)) return { color: '#c62828', bg: '#ffebee' };
  if (/REWORK/.test(action)) return { color: '#e65100', bg: '#fff3e0' };
  if (/OVERRIDE/.test(action)) return { color: '#6a1b9a', bg: '#f3e5f5' };
  return { color: '#455a64', bg: '#eceff1' };
};

const InlineAuditTrail = ({ item }: { item: any }) => {
  const { data: trail = [], isLoading } = useQuery({
    queryKey: ['approval-audit', item.status_id],
    queryFn: () => controlApi.auditTrail(item.status_id).then((r) => r.data),
    enabled: true,
  });

  const approverRows = [
    { level: 'L1', name: item.l1_approver_name, id: item.l1_approver_id, action: item.l1_action },
    { level: 'L2', name: item.l2_approver_name, id: item.l2_approver_id, action: item.l2_action },
    { level: 'L3', name: item.l3_approver_name, id: item.l3_approver_id, action: item.l3_action },
  ].filter((r) => r.id);

  return (
    <Box sx={{ px: 3, py: 2, bgcolor: '#fafafa', borderTop: '1px solid', borderColor: 'divider' }}>
      {approverRows.length > 0 && (
        <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
          {approverRows.map((r) => {
            const c = r.action ? actionColor(r.action) : { color: '#455a64', bg: '#eceff1' };
            return (
              <Box key={r.level} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Chip label={r.level} size="small" variant="outlined" sx={{ fontWeight: 700, fontSize: '0.68rem', minWidth: 28 }} />
                <Typography variant="caption" sx={{ fontWeight: 600 }}>{r.name || `User #${r.id}`}</Typography>
                {r.action && (
                  <Chip label={r.action} size="small"
                    sx={{ bgcolor: c.bg, color: c.color, fontWeight: 700, fontSize: '0.68rem' }} />
                )}
              </Box>
            );
          })}
          <Typography variant="caption" sx={{ color: 'text.secondary', alignSelf: 'center' }}>
            Submitted by: <strong>{item.submitted_by_name || `User #${item.submitted_by}`}</strong>
          </Typography>
        </Box>
      )}

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
        <History sx={{ fontSize: 15, color: 'text.secondary' }} />
        <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Audit Trail
        </Typography>
      </Box>
      {isLoading ? (
        <CircularProgress size={18} />
      ) : trail.length === 0 ? (
        <Typography variant="caption" sx={{ color: 'text.disabled' }}>No audit records yet.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 220 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', py: 0.5 }}>Action</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', py: 0.5 }}>Performed By</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', py: 0.5 }}>Date</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', py: 0.5 }}>Status Change</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', py: 0.5 }}>Comments</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(trail as any[]).map((a: any) => {
                const c = actionColor(a.action);
                return (
                  <TableRow key={a.audit_id} hover>
                    <TableCell sx={{ py: 0.5 }}>
                      <Chip label={a.action} size="small"
                        sx={{ bgcolor: c.bg, color: c.color, fontWeight: 700, fontSize: '0.68rem' }} />
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.78rem', py: 0.5 }}>
                      {a.performer_name || `User #${a.performed_by}`}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap', py: 0.5 }}>
                      {new Date(a.performed_dt).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }}>
                      {a.previous_status && a.new_status
                        ? <span>{a.previous_status} → <strong>{a.new_status}</strong></span>
                        : a.new_status || '—'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', maxWidth: 200, py: 0.5 }}>
                      <Typography noWrap variant="caption" title={a.comments}>{a.comments || '—'}</Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

// ─── Month names ─────────────────────────────────────────────
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export default function ApprovalsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAppSelector((s) => s.auth);

  // Outer section: "My Approvals" vs "Approvals History"
  const [section, setSection] = useState<'active' | 'history'>('active');

  // My Approvals — active level tab
  const [level, setLevel] = useState<'L1' | 'L2' | 'L3'>(() => {
    const roles = user?.roles || [];
    if (hasRole(roles, ['L3_ADMIN', 'SYSTEM_ADMIN'])) return 'L3';
    if (hasRole(roles, ['L2_APPROVER'])) return 'L2';
    return 'L1';
  });

  // Active queue filters
  const [activeYear, setActiveYear] = useState<number | ''>('');
  const [activeMonth, setActiveMonth] = useState<number | ''>('');
  const [activeRegionId, setActiveRegionId] = useState<number | ''>('');
  const [activePage, setActivePage] = useState(1);

  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [actionDialog, setActionDialog] = useState<{
    open: boolean; submissionId: number | null; action: string; item?: any;
  }>({ open: false, submissionId: null, action: '' });
  const [comments, setComments] = useState('');
  const [commentsTouched, setCommentsTouched] = useState(false);
  const [nextApproverId, setNextApproverId] = useState<number | null>(null);
  const [commentDialog, setCommentDialog] = useState<{ open: boolean; statusId: number | null; kriId: number | null }>({
    open: false, statusId: null, kriId: null,
  });
  const [commentText, setCommentText] = useState('');

  // Active queue inline column filters
  const [activeColFilters, setActiveColFilters] = useState({
    kri: '',
    dimension: '',
    region: '',
    status: '',
    submittedBy: '',
  });

  // History inline column filters
  const [historyColFilters, setHistoryColFilters] = useState({
    kri: '',
    dimension: '',
    submittedBy: '',
    action: '',
    finalStatus: '',
  });

  // History filters
  const [historyLevel, setHistoryLevel] = useState<'L1' | 'L2' | 'L3'>(() => {
    const roles = user?.roles || [];
    if (hasRole(roles, ['L3_ADMIN', 'SYSTEM_ADMIN'])) return 'L3';
    if (hasRole(roles, ['L2_APPROVER'])) return 'L2';
    return 'L1';
  });
  const [historyYear, setHistoryYear] = useState<number | ''>('');
  const [historyMonth, setHistoryMonth] = useState<number | ''>('');
  const [historyPage, setHistoryPage] = useState(1);

  // ─── Queries ─────────────────────────────────────────────
  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ['pending-approvals', level, activeYear, activeMonth, activeRegionId, activePage],
    queryFn: () => makerCheckerApi.pending({
      level,
      year: activeYear || undefined,
      month: activeMonth || undefined,
      region_id: activeRegionId || undefined,
      page: activePage,
      page_size: 25,
    }).then((r) => r.data),
    enabled: section === 'active',
  });

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['approval-history', historyLevel, historyYear, historyMonth, historyPage],
    queryFn: () => makerCheckerApi.history({
      level: historyLevel,
      year: historyYear || undefined,
      month: historyMonth || undefined,
      page: historyPage,
      page_size: 25,
    }).then((r) => r.data),
    enabled: section === 'history',
  });

  const { data: regionsData = [] } = useQuery({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: l2Users = [] } = useQuery({
    queryKey: ['l2-users'],
    queryFn: () => userApi.byRole('L2_APPROVER').then((r) => r.data),
  });

  const { data: l3Users = [] } = useQuery({
    queryKey: ['l3-users'],
    queryFn: () => userApi.byRole('L3_ADMIN').then((r) => r.data),
  });

  // ─── Mutations ───────────────────────────────────────────
  const actionMutation = useMutation({
    mutationFn: (params: { id: number; action: string; comments: string; next_approver_id?: number }) =>
      makerCheckerApi.action(params.id, {
        action: params.action,
        comments: params.comments,
        next_approver_id: params.next_approver_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-approvals'] });
      setActionDialog({ open: false, submissionId: null, action: '' });
      setComments('');
      setCommentsTouched(false);
      setNextApproverId(null);
    },
  });

  const commentMutation = useMutation({
    mutationFn: (params: { kri_id: number; status_id: number; text: string }) =>
      commentApi.add({ kri_id: params.kri_id, status_id: params.status_id, comment_text: params.text, comment_type: 'APPROVAL' }),
    onSuccess: () => {
      setCommentDialog({ open: false, statusId: null, kriId: null });
      setCommentText('');
    },
  });

  const activeItems = pendingData?.items || [];
  const activeTotal = pendingData?.total || 0;
  const historyItems = historyData?.items || [];
  const historyTotal = historyData?.total || 0;

  // Apply client-side column filters on top of API results
  const filteredActiveItems = useMemo(() => {
    return activeItems.filter((item: any) => {
      if (activeColFilters.kri) {
        const s = activeColFilters.kri.toLowerCase();
        if (!item.kri_name?.toLowerCase().includes(s) && !item.kri_code?.toLowerCase().includes(s)) return false;
      }
      if (activeColFilters.dimension && !item.dimension_name?.toLowerCase().includes(activeColFilters.dimension.toLowerCase())) return false;
      if (activeColFilters.region && item.region_name !== activeColFilters.region) return false;
      if (activeColFilters.status && item.final_status !== activeColFilters.status) return false;
      if (activeColFilters.submittedBy && !item.submitted_by_name?.toLowerCase().includes(activeColFilters.submittedBy.toLowerCase())) return false;
      return true;
    });
  }, [activeItems, activeColFilters]);

  const filteredHistoryItems = useMemo(() => {
    return historyItems.filter((item: any) => {
      if (historyColFilters.kri) {
        const s = historyColFilters.kri.toLowerCase();
        if (!item.kri_name?.toLowerCase().includes(s) && !item.kri_code?.toLowerCase().includes(s)) return false;
      }
      if (historyColFilters.dimension && !item.dimension_name?.toLowerCase().includes(historyColFilters.dimension.toLowerCase())) return false;
      if (historyColFilters.submittedBy && !item.submitted_by_name?.toLowerCase().includes(historyColFilters.submittedBy.toLowerCase())) return false;
      if (historyColFilters.action && item.action !== historyColFilters.action) return false;
      if (historyColFilters.finalStatus && item.final_status !== historyColFilters.finalStatus) return false;
      return true;
    });
  }, [historyItems, historyColFilters]);
  const nextApprovers = level === 'L1' ? l2Users : level === 'L2' ? l3Users : [];

  const canApprove = hasRole(user?.roles || [], ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']);
  const canEscalate = isL3Admin(user?.roles || []);
  const isAdmin = hasRole(user?.roles || [], ['L3_ADMIN', 'SYSTEM_ADMIN']);

  const periods = getAvailablePeriods(24);
  const availableYears = Array.from(new Set(periods.map((p) => p.year)));

  const hasActiveFilters = activeYear !== '' || activeMonth !== '' || activeRegionId !== '';

  const clearActiveFilters = () => {
    setActiveYear('');
    setActiveMonth('');
    setActiveRegionId('');
    setActivePage(1);
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>Approvals Queue</Typography>

      {/* ─── Outer section tabs ─────────────────────────────── */}
      <Box sx={{ borderBottom: '2px solid', borderColor: 'divider', mb: 0 }}>
        <Tabs
          value={section}
          onChange={(_, v) => setSection(v)}
          sx={{ '& .MuiTab-root': { fontWeight: 700, fontSize: '0.9rem' } }}
        >
          <Tab label="My Approvals" value="active" />
          <Tab label="Approvals History" value="history" icon={<History sx={{ fontSize: 18 }} />} iconPosition="start" />
        </Tabs>
      </Box>

      {/* ═══════════════════════════════════════════════════════
          MY APPROVALS — active queue with filters
      ════════════════════════════════════════════════════════ */}
      {section === 'active' && (
        <Card sx={{ mt: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
          <CardContent sx={{ p: 0 }}>
            {/* Level tabs */}
            <Tabs
              value={level}
              onChange={(_, v) => { setLevel(v); setActivePage(1); }}
              sx={{ borderBottom: '1px solid', borderColor: 'divider' }}
            >
              {hasRole(user?.roles || [], ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']) && (
                <Tab label="L1 Approver" value="L1" />
              )}
              {hasRole(user?.roles || [], ['L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']) && (
                <Tab label="L2 Approver" value="L2" />
              )}
              {hasRole(user?.roles || [], ['L3_ADMIN', 'SYSTEM_ADMIN']) && (
                <Tab label="L3 / Admin" value="L3" />
              )}
            </Tabs>

            {/* ─── Active Queue Filter Bar ───────────────────── */}
            <Box sx={{
              display: 'flex', gap: 2, p: 2, alignItems: 'center', flexWrap: 'wrap',
              borderBottom: '1px solid', borderColor: 'divider', bgcolor: '#fafafa',
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <FilterAlt sx={{ fontSize: 16, color: 'text.secondary' }} />
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Filters
                </Typography>
              </Box>

              {/* Reporting Month — Year */}
              <FormControl size="small" sx={{ minWidth: 110 }}>
                <InputLabel>Year</InputLabel>
                <Select
                  value={activeYear}
                  label="Year"
                  onChange={(e) => { setActiveYear(e.target.value as number | ''); setActivePage(1); }}
                >
                  <MenuItem value="">All Years</MenuItem>
                  {availableYears.map((y) => (
                    <MenuItem key={y} value={y}>{y}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Reporting Month */}
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel>Reporting Month</InputLabel>
                <Select
                  value={activeMonth}
                  label="Reporting Month"
                  onChange={(e) => { setActiveMonth(e.target.value as number | ''); setActivePage(1); }}
                >
                  <MenuItem value="">All Months</MenuItem>
                  {MONTHS.map((name, idx) => (
                    <MenuItem key={idx + 1} value={idx + 1}>{name}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Legal Entity */}
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel>Legal Entity</InputLabel>
                <Select
                  value={activeRegionId}
                  label="Legal Entity"
                  onChange={(e) => { setActiveRegionId(e.target.value as number | ''); setActivePage(1); }}
                >
                  <MenuItem value="">All Entities</MenuItem>
                  {(regionsData as any[]).map((r: any) => (
                    <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {hasActiveFilters && (
                <Tooltip title="Clear all filters">
                  <IconButton size="small" onClick={clearActiveFilters}>
                    <FilterAltOff fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}

              {activeTotal > 0 && (
                <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
                  {activeTotal} item{activeTotal !== 1 ? 's' : ''}
                  {hasActiveFilters ? ' (filtered)' : ''}
                </Typography>
              )}
            </Box>

            <Box sx={{ p: 2 }}>
              {pendingLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
              ) : activeItems.length === 0 ? (
                <Alert severity="success" sx={{ mt: 1 }}>
                  {hasActiveFilters
                    ? 'No pending approvals match the selected filters.'
                    : `No pending ${level} approvals. All caught up!`}
                </Alert>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ width: 32 }} />
                        <TableCell sx={{ fontWeight: 700 }}>KRI</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Control / Dimension</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Legal Entity</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Reporting Month</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Submitted</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Submitted By</TableCell>
                        <TableCell sx={{ fontWeight: 700, minWidth: 130 }} align="center">Actions</TableCell>
                      </TableRow>
                      <TableHeaderFilters
                        filters={[
                          { key: '_expand', label: '', type: 'none', value: '', onChange: () => {} },
                          { key: 'kri', label: 'KRI', type: 'text', value: activeColFilters.kri,
                            onChange: (v) => setActiveColFilters((f) => ({ ...f, kri: v })) },
                          { key: 'dimension', label: 'Dimension', type: 'text', value: activeColFilters.dimension,
                            onChange: (v) => setActiveColFilters((f) => ({ ...f, dimension: v })) },
                          { key: 'region', label: 'Legal Entity', type: 'select',
                            options: (regionsData as any[]).map((r: any) => ({ value: r.region_name, label: r.region_name })),
                            value: activeColFilters.region,
                            onChange: (v) => setActiveColFilters((f) => ({ ...f, region: v })) },
                          { key: '_month', label: '', type: 'none', value: '', onChange: () => {} },
                          { key: 'status', label: 'Status', type: 'select',
                            options: [
                              { value: 'L1_PENDING', label: 'L1 Pending' },
                              { value: 'L2_PENDING', label: 'L2 Pending' },
                              { value: 'L3_PENDING', label: 'L3 Pending' },
                              { value: 'APPROVED', label: 'Approved' },
                              { value: 'REJECTED', label: 'Rejected' },
                              { value: 'REWORK', label: 'Rework' },
                            ],
                            value: activeColFilters.status,
                            onChange: (v) => setActiveColFilters((f) => ({ ...f, status: v })) },
                          { key: '_submitted', label: '', type: 'none', value: '', onChange: () => {} },
                          { key: 'submittedBy', label: 'Submitted By', type: 'text', value: activeColFilters.submittedBy,
                            onChange: (v) => setActiveColFilters((f) => ({ ...f, submittedBy: v })) },
                          { key: '_actions', label: '', type: 'none', value: '', onChange: () => {} },
                        ]}
                      />
                    </TableHead>
                    <TableBody>
                      {filteredActiveItems.map((item: any) => (
                        <React.Fragment key={item.submission_id}>
                          <TableRow hover sx={{ '& > *': { borderBottom: expandedRow === item.submission_id ? 'unset' : undefined } }}>
                            <TableCell>
                              <IconButton
                                size="small"
                                onClick={() => setExpandedRow(expandedRow === item.submission_id ? null : item.submission_id)}
                              >
                                {expandedRow === item.submission_id ? <KeyboardArrowUp /> : <KeyboardArrowDown />}
                              </IconButton>
                            </TableCell>

                            {/* KRI name + code only, no brackets */}
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                                {item.kri_name || `Status #${item.status_id}`}
                              </Typography>
                              {item.kri_code && (
                                <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                  {item.kri_code}
                                </Typography>
                              )}
                            </TableCell>

                            {/* Control / Dimension name */}
                            <TableCell sx={{ fontSize: '0.82rem' }}>
                              {item.dimension_name || '—'}
                            </TableCell>

                            {/* Legal Entity (region) */}
                            <TableCell sx={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                              {item.region_name || '—'}
                            </TableCell>

                            {/* Reporting Month */}
                            <TableCell sx={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                              {item.period_year && item.period_month
                                ? `${MONTHS[item.period_month - 1]} ${item.period_year}`
                                : '—'}
                            </TableCell>

                            {/* Status */}
                            <TableCell>{statusChip(item.final_status)}</TableCell>

                            {/* Submitted — date + time */}
                            <TableCell sx={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                              {new Date(item.submitted_dt).toLocaleString('en-GB', {
                                day: '2-digit', month: 'short', year: 'numeric',
                                hour: '2-digit', minute: '2-digit',
                              })}
                            </TableCell>

                            <TableCell sx={{ fontSize: '0.82rem' }}>
                              {item.submitted_by_name || `User #${item.submitted_by}`}
                            </TableCell>

                            {/* ─── Actions: compact icon buttons ─── */}
                            <TableCell align="center">
                              <Box sx={{ display: 'flex', gap: 0.4, justifyContent: 'center', alignItems: 'center', flexWrap: 'nowrap' }}>
                                {canApprove && (
                                  <>
                                    <Tooltip title="Approve">
                                      <IconButton
                                        size="small" color="success" aria-label="Approve"
                                        onClick={() => {
                                          const preselected = level === 'L1' ? (item.l2_approver_id || null) : level === 'L2' ? (item.l3_approver_id || null) : null;
                                          setNextApproverId(preselected);
                                          setActionDialog({ open: true, submissionId: item.submission_id, action: 'APPROVED', item });
                                        }}
                                        sx={{ border: '1px solid', borderColor: 'success.light', borderRadius: 1.5, p: 0.5 }}
                                      >
                                        <CheckCircle fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Send for Rework">
                                      <IconButton
                                        size="small" color="warning" aria-label="Rework"
                                        onClick={() => { setNextApproverId(null); setActionDialog({ open: true, submissionId: item.submission_id, action: 'REWORK', item }); }}
                                        sx={{ border: '1px solid', borderColor: 'warning.light', borderRadius: 1.5, p: 0.5 }}
                                      >
                                        <Replay fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Reject">
                                      <IconButton
                                        size="small" color="error" aria-label="Reject"
                                        onClick={() => { setNextApproverId(null); setActionDialog({ open: true, submissionId: item.submission_id, action: 'REJECTED', item }); }}
                                        sx={{ border: '1px solid', borderColor: 'error.light', borderRadius: 1.5, p: 0.5 }}
                                      >
                                        <Cancel fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                  </>
                                )}
                                {canEscalate && level !== 'L3' && (
                                  <Tooltip title="Escalate">
                                    <IconButton
                                      size="small" color="info" aria-label="Escalate"
                                      onClick={() => { setNextApproverId(null); setActionDialog({ open: true, submissionId: item.submission_id, action: 'ESCALATE', item }); }}
                                      sx={{ border: '1px solid', borderColor: 'info.light', borderRadius: 1.5, p: 0.5 }}
                                    >
                                      <ArrowForward fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                )}
                                <Tooltip title="View Evidence">
                                  <IconButton size="small" onClick={() => navigate('/evidence')} aria-label="View Evidence">
                                    <Folder fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Add Comment">
                                  <IconButton size="small" aria-label="Add Comment" onClick={() => {
                                    setCommentDialog({ open: true, statusId: item.status_id, kriId: item.kri_id });
                                    setCommentText('');
                                  }}>
                                    <Comment fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            </TableCell>
                          </TableRow>

                          {/* Expandable Audit Trail — colSpan updated to 9 */}
                          <TableRow>
                            <TableCell colSpan={9} sx={{ p: 0, border: 0 }}>
                              <Collapse in={expandedRow === item.submission_id} timeout="auto" unmountOnExit>
                                <InlineAuditTrail item={item} />
                              </Collapse>
                            </TableCell>
                          </TableRow>
                        </React.Fragment>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {/* Active queue pagination */}
              {activeTotal > 25 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', pt: 2 }}>
                  <Pagination
                    count={Math.ceil(activeTotal / 25)}
                    page={activePage}
                    onChange={(_, p) => setActivePage(p)}
                    color="primary"
                    size="small"
                  />
                </Box>
              )}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* ═══════════════════════════════════════════════════════
          APPROVALS HISTORY
      ════════════════════════════════════════════════════════ */}
      {section === 'history' && (
        <Card sx={{ mt: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
          <CardContent sx={{ p: 0 }}>
            {/* ─── History filters ──────────────────────────── */}
            <Box sx={{
              display: 'flex', gap: 2, p: 2, alignItems: 'center', flexWrap: 'wrap',
              borderBottom: '1px solid', borderColor: 'divider', bgcolor: '#fafafa',
            }}>
              {/* Level filter */}
              <FormControl size="small" sx={{ minWidth: 130 }}>
                <InputLabel>Approval Level</InputLabel>
                <Select
                  value={historyLevel}
                  label="Approval Level"
                  onChange={(e) => { setHistoryLevel(e.target.value as 'L1' | 'L2' | 'L3'); setHistoryPage(1); }}
                >
                  {hasRole(user?.roles || [], ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']) && (
                    <MenuItem value="L1">L1 Approver</MenuItem>
                  )}
                  {hasRole(user?.roles || [], ['L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']) && (
                    <MenuItem value="L2">L2 Approver</MenuItem>
                  )}
                  {hasRole(user?.roles || [], ['L3_ADMIN', 'SYSTEM_ADMIN']) && (
                    <MenuItem value="L3">L3 / Admin</MenuItem>
                  )}
                </Select>
              </FormControl>

              {/* Reporting Month filter */}
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Year</InputLabel>
                <Select
                  value={historyYear}
                  label="Year"
                  onChange={(e) => { setHistoryYear(e.target.value as number | ''); setHistoryPage(1); }}
                >
                  <MenuItem value="">All Years</MenuItem>
                  {availableYears.map((y) => (
                    <MenuItem key={y} value={y}>{y}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 130 }}>
                <InputLabel>Reporting Month</InputLabel>
                <Select
                  value={historyMonth}
                  label="Reporting Month"
                  onChange={(e) => { setHistoryMonth(e.target.value as number | ''); setHistoryPage(1); }}
                >
                  <MenuItem value="">All Months</MenuItem>
                  {MONTHS.map((name, idx) => (
                    <MenuItem key={idx + 1} value={idx + 1}>{name}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {(historyYear !== '' || historyMonth !== '') && (
                <Button
                  size="small" variant="outlined"
                  onClick={() => { setHistoryYear(''); setHistoryMonth(''); setHistoryPage(1); }}
                  sx={{ fontSize: '0.75rem' }}
                >
                  Clear Filters
                </Button>
              )}

              {historyTotal > 0 && (
                <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
                  {historyTotal} record{historyTotal !== 1 ? 's' : ''} found
                </Typography>
              )}
            </Box>

            {/* ─── History table ────────────────────────────── */}
            <Box sx={{ p: 2 }}>
              {historyLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
              ) : historyItems.length === 0 ? (
                <Alert severity="info">
                  No completed approvals found{historyYear || historyMonth ? ' for the selected period' : ''}.
                </Alert>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>KRI</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Control / Dimension</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Period</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Submitted By</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Submitted</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Action Taken</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Actioned On</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Final Status</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Comments</TableCell>
                        {isAdmin && (
                          <>
                            <TableCell sx={{ fontWeight: 700 }}>L1</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>L2</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>L3</TableCell>
                          </>
                        )}
                      </TableRow>
                      <TableHeaderFilters
                        filters={[
                          { key: 'kri', label: 'KRI', type: 'text', value: historyColFilters.kri,
                            onChange: (v) => setHistoryColFilters((f) => ({ ...f, kri: v })) },
                          { key: 'dimension', label: 'Control / Dimension', type: 'text', value: historyColFilters.dimension,
                            onChange: (v) => setHistoryColFilters((f) => ({ ...f, dimension: v })) },
                          { key: '_period', label: '', type: 'none', value: '', onChange: () => {} },
                          { key: 'submittedBy', label: 'Submitted By', type: 'text', value: historyColFilters.submittedBy,
                            onChange: (v) => setHistoryColFilters((f) => ({ ...f, submittedBy: v })) },
                          { key: '_submitted', label: '', type: 'none', value: '', onChange: () => {} },
                          { key: 'action', label: 'Action', type: 'select',
                            options: [
                              { value: 'APPROVED', label: 'Approved' },
                              { value: 'REJECTED', label: 'Rejected' },
                              { value: 'REWORK', label: 'Rework' },
                              { value: 'ESCALATE', label: 'Escalate' },
                            ],
                            value: historyColFilters.action,
                            onChange: (v) => setHistoryColFilters((f) => ({ ...f, action: v })) },
                          { key: '_actionedOn', label: '', type: 'none', value: '', onChange: () => {} },
                          { key: 'finalStatus', label: 'Final Status', type: 'select',
                            options: [
                              { value: 'APPROVED', label: 'Approved' },
                              { value: 'REJECTED', label: 'Rejected' },
                              { value: 'REWORK', label: 'Rework' },
                              { value: 'L1_PENDING', label: 'L1 Pending' },
                              { value: 'L2_PENDING', label: 'L2 Pending' },
                              { value: 'L3_PENDING', label: 'L3 Pending' },
                            ],
                            value: historyColFilters.finalStatus,
                            onChange: (v) => setHistoryColFilters((f) => ({ ...f, finalStatus: v })) },
                          { key: '_comments', label: '', type: 'none', value: '', onChange: () => {} },
                          ...(isAdmin ? [
                            { key: '_l1', label: '', type: 'none' as const, value: '', onChange: () => {} },
                            { key: '_l2', label: '', type: 'none' as const, value: '', onChange: () => {} },
                            { key: '_l3', label: '', type: 'none' as const, value: '', onChange: () => {} },
                          ] : []),
                        ]}
                      />
                    </TableHead>
                    <TableBody>
                      {filteredHistoryItems.map((item: any) => (
                        <TableRow key={item.submission_id} hover>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.82rem' }}>
                              {item.kri_name || `Status #${item.status_id}`}
                            </Typography>
                            {item.kri_code && (
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                {item.kri_code}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.82rem' }}>
                            {item.dimension_name || '—'}
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                            {item.period_year && item.period_month
                              ? `${MONTHS[item.period_month - 1]} ${item.period_year}`
                              : '—'}
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.82rem' }}>
                            {item.submitted_by_name || `User #${item.submitted_by}`}
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                            {new Date(item.submitted_dt).toLocaleString('en-GB', {
                              day: '2-digit', month: 'short', year: 'numeric',
                              hour: '2-digit', minute: '2-digit',
                            })}
                          </TableCell>
                          <TableCell>{actionChip(item.action)}</TableCell>
                          <TableCell sx={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                            {item.action_dt
                              ? new Date(item.action_dt).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
                              : '—'}
                          </TableCell>
                          <TableCell>{statusChip(item.final_status)}</TableCell>
                          <TableCell sx={{ fontSize: '0.78rem', maxWidth: 200 }}>
                            <Typography noWrap variant="caption" title={item.comments}>
                              {item.comments || '—'}
                            </Typography>
                          </TableCell>
                          {isAdmin && (
                            <>
                              <TableCell sx={{ fontSize: '0.75rem' }}>
                                {item.l1_action ? (
                                  <Box>
                                    {actionChip(item.l1_action)}
                                    <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                                      {item.l1_approver_name || '—'}
                                    </Typography>
                                  </Box>
                                ) : '—'}
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.75rem' }}>
                                {item.l2_action ? (
                                  <Box>
                                    {actionChip(item.l2_action)}
                                    <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                                      {item.l2_approver_name || '—'}
                                    </Typography>
                                  </Box>
                                ) : '—'}
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.75rem' }}>
                                {item.l3_action ? (
                                  <Box>
                                    {actionChip(item.l3_action)}
                                    <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                                      {item.l3_approver_name || '—'}
                                    </Typography>
                                  </Box>
                                ) : '—'}
                              </TableCell>
                            </>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {historyTotal > 25 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', pt: 2 }}>
                  <Pagination
                    count={Math.ceil(historyTotal / 25)}
                    page={historyPage}
                    onChange={(_, p) => setHistoryPage(p)}
                    color="primary"
                    size="small"
                  />
                </Box>
              )}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* ─── Action Confirmation Dialog ───────────────────── */}
      <Dialog
        open={actionDialog.open}
        onClose={() => {
          setActionDialog({ open: false, submissionId: null, action: '' });
          setComments('');
          setCommentsTouched(false);
          setNextApproverId(null);
        }}
        maxWidth="sm" fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          Confirm: {actionDialog.action} — Submission #{actionDialog.submissionId}
        </DialogTitle>
        <DialogContent dividers>
          <TextField
            label="Comments *"
            multiline rows={3} fullWidth
            value={comments}
            onChange={(e) => { setComments(e.target.value); setCommentsTouched(true); }}
            onBlur={() => setCommentsTouched(true)}
            sx={{ mb: 2 }}
            required
            error={commentsTouched && !comments.trim()}
            helperText={
              commentsTouched && !comments.trim()
                ? 'A comment is required before submitting this action'
                : 'Please explain the reason for this action'
            }
            placeholder="Required: describe the reason for this action..."
          />

          {/* ── APPROVED: L1 / L2 must select the next approver ── */}
          {actionDialog.action === 'APPROVED' && level !== 'L3' && (
            <FormControl fullWidth required sx={{ mt: 1 }} error={!nextApproverId}>
              <InputLabel error={!nextApproverId}>
                Assign to {level === 'L1' ? 'L2' : 'L3'} Approver *
              </InputLabel>
              <Select
                value={nextApproverId || ''}
                label={`Assign to ${level === 'L1' ? 'L2' : 'L3'} Approver *`}
                onChange={(e) => setNextApproverId(Number(e.target.value))}
                error={!nextApproverId}
              >
                {nextApprovers.map((u: any) => (
                  <MenuItem key={u.user_id} value={u.user_id}>{u.full_name} ({u.soe_id})</MenuItem>
                ))}
              </Select>
              {!nextApproverId && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                  Required: select who this submission is forwarded to for {level === 'L1' ? 'L2' : 'L3'} review
                </Typography>
              )}
            </FormControl>
          )}
          {actionDialog.action === 'APPROVED' && level === 'L3' && (
            <Alert severity="info" sx={{ mt: 1 }}>
              L3 is the final approval level. Confirming will fully approve this submission — no further assignment is required.
            </Alert>
          )}

          {/* ── REWORK: informational only — routing is fixed by business rules ── */}
          {actionDialog.action === 'REWORK' && (
            <Alert severity="warning" sx={{ mt: 1 }}>
              {level === 'L1'
                ? 'This will be marked for rework. The data submitter will need to correct the data and resubmit.'
                : level === 'L2'
                  ? `This will be sent back to L1 for re-review. L1 Approver: ${actionDialog.item?.l1_approver_name || 'the assigned L1 approver'}.`
                  : `This will reset the full approval chain to L1. L1 Approver: ${actionDialog.item?.l1_approver_name || 'the assigned L1 approver'} will need to re-review after data correction.`
              }
            </Alert>
          )}

          {/* ── ESCALATE: select target approver (required) ── */}
          {actionDialog.action === 'ESCALATE' && nextApprovers.length > 0 && (
            <FormControl fullWidth required sx={{ mt: 1 }}>
              <InputLabel error={!nextApproverId}>Escalate to (required) *</InputLabel>
              <Select
                value={nextApproverId || ''}
                label="Escalate to (required) *"
                onChange={(e) => setNextApproverId(Number(e.target.value))}
                error={!nextApproverId}
              >
                {nextApprovers.map((u: any) => (
                  <MenuItem key={u.user_id} value={u.user_id}>{u.full_name} ({u.soe_id})</MenuItem>
                ))}
              </Select>
              {!nextApproverId && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                  Select the approver to escalate this submission to
                </Typography>
              )}
            </FormControl>
          )}
          {actionDialog.action === 'ESCALATE' && nextApprovers.length === 0 && (
            <Alert severity="warning" sx={{ mt: 1 }}>
              No eligible approvers found for escalation. Please assign an approver in system settings.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setActionDialog({ open: false, submissionId: null, action: '' });
            setComments('');
            setCommentsTouched(false);
            setNextApproverId(null);
          }}>Cancel</Button>
          <Button
            variant="contained"
            color={
              actionDialog.action === 'APPROVED' ? 'success'
              : actionDialog.action === 'REJECTED' ? 'error'
              : actionDialog.action === 'ESCALATE' ? 'info'
              : 'warning'
            }
            disabled={
              actionMutation.isPending ||
              !comments.trim() ||
              (actionDialog.action === 'APPROVED' && level !== 'L3' && !nextApproverId) ||
              (actionDialog.action === 'ESCALATE' && nextApprovers.length > 0 && !nextApproverId)
            }
            onClick={() => {
              if (!actionDialog.submissionId) return;
              if (!comments.trim()) { setCommentsTouched(true); return; }
              actionMutation.mutate({
                id: actionDialog.submissionId,
                action: actionDialog.action,
                comments,
                next_approver_id: nextApproverId || undefined,
              });
            }}
          >
            {actionMutation.isPending ? 'Processing...' : `Confirm ${actionDialog.action}`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Add Comment Dialog ───────────────────────────── */}
      <Dialog
        open={commentDialog.open}
        onClose={() => setCommentDialog({ open: false, statusId: null, kriId: null })}
        maxWidth="sm" fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Add Comment</DialogTitle>
        <DialogContent dividers>
          <TextField
            label="Comment" multiline rows={4} fullWidth
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Enter your comment..."
            autoFocus
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCommentDialog({ open: false, statusId: null, kriId: null })}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!commentText.trim() || commentMutation.isPending}
            onClick={() => {
              if (commentDialog.kriId && commentDialog.statusId) {
                commentMutation.mutate({
                  kri_id: commentDialog.kriId,
                  status_id: commentDialog.statusId,
                  text: commentText,
                });
              }
            }}
          >
            {commentMutation.isPending ? 'Saving...' : 'Add Comment'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
