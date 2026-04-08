import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, Button, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Select, MenuItem, FormControl, InputLabel,
  Tabs, Tab, Divider, LinearProgress, Tooltip, IconButton, Collapse,
} from '@mui/material';
import {
  CheckCircle, Cancel, Replay, Send, Add, BarChart,
  KeyboardArrowDown, KeyboardArrowUp, History,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useAppSelector } from '../../store';
import { hasRole } from '../../utils/helpers';

// ─── API client (inline — avoids touching client.ts for now) ────────────────
const scorecardApi = {
  list:    (p?: object) => api.get('/scorecard', { params: p }),
  get:     (id: number) => api.get(`/scorecard/${id}`),
  create:  (d: object) => api.post('/scorecard', d),
  submit:  (id: number, notes?: string) => api.post(`/scorecard/${id}/submit`, { notes }),
  approve: (id: number, comments?: string) => api.post(`/scorecard/${id}/approve`, { comments }),
  reject:  (id: number, comments: string) => api.post(`/scorecard/${id}/reject`, { comments }),
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
];

const now = new Date();

const ragChip = (rag: string | null) => {
  const map: Record<string, { bg: string; color: string }> = {
    GREEN: { bg: '#e8f5e9', color: '#2e7d32' },
    AMBER: { bg: '#fff8e1', color: '#f57c00' },
    RED:   { bg: '#ffebee', color: '#c62828' },
    GREY:  { bg: '#f5f5f5', color: '#757575' },
  };
  const s = map[rag || 'GREY'] || map.GREY;
  return (
    <Chip label={rag || 'N/A'} size="small"
      sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, fontSize: '0.7rem', minWidth: 52 }} />
  );
};

const statusChip = (status: string) => {
  const map: Record<string, { label: string; bg: string; color: string }> = {
    DRAFT:      { label: 'Draft',      bg: '#e3f2fd', color: '#1565c0' },
    L1_PENDING: { label: 'Pending Review', bg: '#fff8e1', color: '#f57c00' },
    L2_PENDING: { label: 'L2 Pending', bg: '#fff3e0', color: '#e65100' },
    APPROVED:   { label: 'Approved',   bg: '#e8f5e9', color: '#2e7d32' },
    REJECTED:   { label: 'Rejected',   bg: '#ffebee', color: '#c62828' },
    REWORK:     { label: 'Rework',     bg: '#fff3e0', color: '#e65100' },
  };
  const s = map[status] || { label: status, bg: '#f5f5f5', color: '#616161' };
  return (
    <Chip label={s.label} size="small"
      sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, fontSize: '0.72rem' }} />
  );
};

const slaBar = (pct: number) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
    <LinearProgress
      variant="determinate" value={Math.min(pct, 100)}
      sx={{
        flex: 1, height: 8, borderRadius: 4,
        bgcolor: '#f5f5f5',
        '& .MuiLinearProgress-bar': {
          bgcolor: pct >= 80 ? '#4caf50' : pct >= 50 ? '#ff9800' : '#f44336',
          borderRadius: 4,
        },
      }}
    />
    <Typography variant="caption" sx={{ fontWeight: 700, minWidth: 36 }}>{pct}%</Typography>
  </Box>
);

// ─── Scorecard detail row (expandable) ───────────────────────────────────────
const ScorecardRow = ({ sc, isChecker, onApprove, onReject }: {
  sc: any;
  isChecker: boolean;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) => {
  const [open, setOpen] = useState(false);
  const { data: detail, isLoading } = useQuery({
    queryKey: ['scorecard-detail', sc.scorecard_id],
    queryFn: () => scorecardApi.get(sc.scorecard_id).then((r) => r.data),
    enabled: open,
  });

  const canAct = isChecker && (sc.final_status === 'L1_PENDING' || sc.final_status === 'L2_PENDING');

  return (
    <>
      <TableRow hover sx={{ cursor: 'pointer' }} onClick={() => setOpen(!open)}>
        <TableCell sx={{ py: 1 }}>
          <IconButton size="small">{open ? <KeyboardArrowUp fontSize="small" /> : <KeyboardArrowDown fontSize="small" />}</IconButton>
        </TableCell>
        <TableCell sx={{ fontWeight: 700, fontSize: '0.82rem' }}>
          {MONTHS[(sc.month ?? 1) - 1]} {sc.year}
        </TableCell>
        <TableCell>{statusChip(sc.final_status)}</TableCell>
        <TableCell sx={{ fontSize: '0.82rem' }}>{sc.submitted_by}</TableCell>
        <TableCell sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
          {sc.submitted_dt ? new Date(sc.submitted_dt).toLocaleDateString('en-GB') : '—'}
        </TableCell>
        <TableCell>{sc.summary?.sla_compliance_pct != null ? slaBar(sc.summary.sla_compliance_pct) : '—'}</TableCell>
        <TableCell>
          {canAct && (
            <Box sx={{ display: 'flex', gap: 1 }} onClick={(e) => e.stopPropagation()}>
              <Tooltip title="Approve">
                <IconButton size="small" color="success" onClick={() => onApprove(sc.scorecard_id)}>
                  <CheckCircle fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Reject">
                <IconButton size="small" color="error" onClick={() => onReject(sc.scorecard_id)}>
                  <Cancel fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </TableCell>
      </TableRow>

      {/* Expandable detail */}
      <TableRow>
        <TableCell colSpan={7} sx={{ py: 0, px: 0 }}>
          <Collapse in={open} unmountOnExit>
            <Box sx={{ px: 3, py: 2, bgcolor: '#fafafa', borderTop: '1px solid', borderColor: 'divider' }}>
              {isLoading ? (
                <CircularProgress size={20} />
              ) : detail ? (
                <>
                  {/* Summary cards */}
                  <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                    {Object.entries(detail.summary?.by_rag || {}).map(([rag, cnt]: [string, any]) => (
                      <Box key={rag} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {ragChip(rag)}
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>{cnt}</Typography>
                      </Box>
                    ))}
                    <Divider orientation="vertical" flexItem />
                    <Typography variant="body2" sx={{ color: 'text.secondary', alignSelf: 'center' }}>
                      Total controls: <strong>{detail.summary?.total_controls}</strong>
                    </Typography>
                  </Box>

                  {/* KRI breakdown table */}
                  {detail.kri_rows?.length > 0 && (
                    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 260, mb: 2 }}>
                      <Table size="small" stickyHeader>
                        <TableHead>
                          <TableRow>
                            {['KRI', 'Control', 'Status', 'RAG', 'SLA Met', 'Due Date'].map((h) => (
                              <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.72rem', py: 0.5, bgcolor: '#f5f5f5' }}>{h}</TableCell>
                            ))}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {detail.kri_rows.map((r: any) => (
                            <TableRow key={r.status_id} hover>
                              <TableCell sx={{ fontSize: '0.78rem', py: 0.5, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                <Tooltip title={r.kri_name || ''}><span>{r.kri_name || `KRI #${r.kri_id}`}</span></Tooltip>
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }}>{r.dimension_name || `Dim #${r.dimension_id}`}</TableCell>
                              <TableCell sx={{ py: 0.5 }}>
                                <Chip label={r.status} size="small" sx={{ fontSize: '0.68rem' }} />
                              </TableCell>
                              <TableCell sx={{ py: 0.5 }}>{ragChip(r.rag_status)}</TableCell>
                              <TableCell sx={{ py: 0.5 }}>
                                {r.sla_met === true ? (
                                  <CheckCircle sx={{ color: '#4caf50', fontSize: 16 }} />
                                ) : r.sla_met === false ? (
                                  <Cancel sx={{ color: '#f44336', fontSize: 16 }} />
                                ) : '—'}
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.75rem', py: 0.5, whiteSpace: 'nowrap' }}>
                                {r.sla_due_dt ? new Date(r.sla_due_dt).toLocaleDateString('en-GB') : '—'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}

                  {/* Audit trail */}
                  {detail.audit_trail?.length > 0 && (
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                        <History sx={{ fontSize: 14, color: 'text.secondary' }} />
                        <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5 }}>Audit Trail</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                        {detail.audit_trail.map((a: any, i: number) => (
                          <Box key={i} sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                            <Chip label={a.action} size="small" sx={{ fontSize: '0.65rem', fontWeight: 700 }} />
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                              {a.performed_by} — {a.performed_dt ? new Date(a.performed_dt).toLocaleString('en-GB') : ''}
                            </Typography>
                            {a.comments && (
                              <Typography variant="caption" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
                                "{a.comments}"
                              </Typography>
                            )}
                          </Box>
                        ))}
                      </Box>
                    </Box>
                  )}
                </>
              ) : null}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function ScorecardPage() {
  const { user } = useAppSelector((s) => s.auth);
  const roles = user?.roles?.map((r: any) => r.role_code) ?? [];
  const queryClient = useQueryClient();

  const isMaker = hasRole(roles, ['SCORECARD_MAKER', 'L1_APPROVER', 'DATA_PROVIDER',
                                   'METRIC_OWNER', 'MANAGEMENT', 'SYSTEM_ADMIN']);
  const isChecker = hasRole(roles, ['SCORECARD_CHECKER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']);

  const [tab, setTab] = useState(0);

  // Period state for new scorecard
  const [selYear, setSelYear] = useState(now.getFullYear());
  const [selMonth, setSelMonth] = useState(now.getMonth() + 1);
  const [selRegion, setSelRegion] = useState<string>('');
  const [draftNotes, setDraftNotes] = useState('');

  // Approve dialog
  const [approveId, setApproveId] = useState<number | null>(null);
  const [approveComments, setApproveComments] = useState('');

  // Reject dialog
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [rejectComments, setRejectComments] = useState('');

  // Submit dialog (maker submits existing draft)
  const [submitId, setSubmitId] = useState<number | null>(null);
  const [submitNotes, setSubmitNotes] = useState('');

  // Error/success
  const [alert, setAlert] = useState<{ severity: 'success' | 'error'; msg: string } | null>(null);

  // ── Queries ───────────────────────────────────────────────
  const { data: allScorecards = { items: [] }, isLoading } = useQuery({
    queryKey: ['scorecards'],
    queryFn: () => scorecardApi.list().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: regions = [] } = useQuery({
    queryKey: ['regions'],
    queryFn: () => api.get('/lookups/regions').then((r) => r.data),
  });

  const scorecards: any[] = allScorecards.items ?? [];
  const pending  = scorecards.filter((s) => ['L1_PENDING', 'L2_PENDING'].includes(s.final_status));
  const myDrafts = scorecards.filter((s) => ['DRAFT', 'REWORK'].includes(s.final_status));
  const approved = scorecards.filter((s) => s.final_status === 'APPROVED');

  // ── Mutations ─────────────────────────────────────────────
  const createMut = useMutation({
    mutationFn: () => scorecardApi.create({
      year: selYear, month: selMonth,
      region_id: selRegion ? Number(selRegion) : null,
      notes: draftNotes || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scorecards'] });
      setAlert({ severity: 'success', msg: 'Scorecard draft created.' });
      setDraftNotes('');
    },
    onError: (e: any) => setAlert({ severity: 'error', msg: e.response?.data?.detail ?? 'Failed to create.' }),
  });

  const submitMut = useMutation({
    mutationFn: (id: number) => scorecardApi.submit(id, submitNotes || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scorecards'] });
      setSubmitId(null); setSubmitNotes('');
      setAlert({ severity: 'success', msg: 'Scorecard submitted for review.' });
    },
    onError: (e: any) => setAlert({ severity: 'error', msg: e.response?.data?.detail ?? 'Submit failed.' }),
  });

  const approveMut = useMutation({
    mutationFn: (id: number) => scorecardApi.approve(id, approveComments || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scorecards'] });
      setApproveId(null); setApproveComments('');
      setAlert({ severity: 'success', msg: 'Scorecard approved.' });
    },
    onError: (e: any) => setAlert({ severity: 'error', msg: e.response?.data?.detail ?? 'Approval failed.' }),
  });

  const rejectMut = useMutation({
    mutationFn: (id: number) => scorecardApi.reject(id, rejectComments),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scorecards'] });
      setRejectId(null); setRejectComments('');
      setAlert({ severity: 'success', msg: 'Scorecard returned for rework.' });
    },
    onError: (e: any) => setAlert({ severity: 'error', msg: e.response?.data?.detail ?? 'Rejection failed.' }),
  });

  // ── Render ────────────────────────────────────────────────
  const tableHeaders = ['', 'Period', 'Status', 'Submitted By', 'Date', 'SLA Compliance', 'Actions'];

  const ScTable = ({ rows }: { rows: any[] }) => (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow sx={{ bgcolor: '#f5f7fa' }}>
            {tableHeaders.map((h) => (
              <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.78rem', py: 1 }}>{h}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4, color: 'text.disabled', fontStyle: 'italic' }}>
                No scorecards found.
              </TableCell>
            </TableRow>
          ) : (
            rows.map((sc) => (
              <ScorecardRow
                key={sc.scorecard_id}
                sc={sc}
                isChecker={isChecker}
                onApprove={(id) => { setApproveId(id); setApproveComments(''); }}
                onReject={(id) => { setRejectId(id); setRejectComments(''); }}
              />
            ))
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 700 }}>Scorecard</Typography>
      <Typography variant="body2" sx={{ mb: 2.5, color: 'text.secondary' }}>
        Monthly KRI health summary — Maker / Checker workflow
      </Typography>

      {alert && (
        <Alert severity={alert.severity} sx={{ mb: 2 }} onClose={() => setAlert(null)}>
          {alert.msg}
        </Alert>
      )}

      {/* ── Create scorecard panel (Maker only) ───────────── */}
      {isMaker && (
        <Card variant="outlined" sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <BarChart sx={{ color: 'primary.main' }} />
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                Compile New Scorecard
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <FormControl size="small" sx={{ minWidth: 110 }}>
                <InputLabel>Year</InputLabel>
                <Select value={selYear} label="Year" onChange={(e) => setSelYear(Number(e.target.value))}>
                  {[now.getFullYear() - 1, now.getFullYear()].map((y) => (
                    <MenuItem key={y} value={y}>{y}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 130 }}>
                <InputLabel>Month</InputLabel>
                <Select value={selMonth} label="Month" onChange={(e) => setSelMonth(Number(e.target.value))}>
                  {MONTHS.map((m, i) => (
                    <MenuItem key={i + 1} value={i + 1}>{m}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Region (optional)</InputLabel>
                <Select value={selRegion} label="Region (optional)" onChange={(e) => setSelRegion(e.target.value as string)}>
                  <MenuItem value=""><em>All Regions</em></MenuItem>
                  {(regions as any[]).map((r) => (
                    <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                size="small" label="Notes (optional)" value={draftNotes}
                onChange={(e) => setDraftNotes(e.target.value)}
                sx={{ minWidth: 220 }}
              />

              <Button
                variant="contained" startIcon={<Add />}
                onClick={() => createMut.mutate()}
                disabled={createMut.isPending}
              >
                {createMut.isPending ? 'Creating…' : 'Create Draft'}
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* ── Tabs ───────────────────────────────────────────── */}
      <Card>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
          {isChecker && (
            <Tab label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                Pending Review
                {pending.length > 0 && (
                  <Chip label={pending.length} size="small"
                    sx={{ bgcolor: '#ff9800', color: '#fff', fontWeight: 700, height: 18, fontSize: '0.68rem' }} />
                )}
              </Box>
            } />
          )}
          {isMaker && <Tab label={`My Drafts${myDrafts.length ? ` (${myDrafts.length})` : ''}`} />}
          <Tab label={`Approved (${approved.length})`} />
          <Tab label={`All (${scorecards.length})`} />
        </Tabs>

        <CardContent sx={{ pt: 2 }}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {/* Pending Review tab */}
              {isChecker && tab === 0 && (
                <>
                  {pending.length > 0 && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                      {pending.length} scorecard{pending.length > 1 ? 's' : ''} awaiting your review.
                    </Alert>
                  )}
                  <ScTable rows={pending} />
                </>
              )}

              {/* My Drafts tab */}
              {isMaker && tab === (isChecker ? 1 : 0) && (
                <>
                  <ScTable rows={myDrafts} />
                  {/* Submit buttons for each draft */}
                  {myDrafts.length > 0 && (
                    <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {myDrafts.map((sc) => (
                        <Button
                          key={sc.scorecard_id}
                          size="small" variant="outlined" startIcon={<Send />}
                          onClick={() => { setSubmitId(sc.scorecard_id); setSubmitNotes(''); }}
                        >
                          Submit {MONTHS[(sc.month ?? 1) - 1]} {sc.year}
                        </Button>
                      ))}
                    </Box>
                  )}
                </>
              )}

              {/* Approved tab */}
              {tab === (isChecker ? (isMaker ? 2 : 1) : (isMaker ? 1 : 0)) && (
                <ScTable rows={approved} />
              )}

              {/* All tab */}
              {tab === (isChecker ? (isMaker ? 3 : 2) : (isMaker ? 2 : 1)) && (
                <ScTable rows={scorecards} />
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* ── Approve dialog ─────────────────────────────────── */}
      <Dialog open={approveId !== null} onClose={() => setApproveId(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CheckCircle color="success" />
          Approve Scorecard
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth multiline rows={3}
            label="Comments (optional)"
            value={approveComments}
            onChange={(e) => setApproveComments(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApproveId(null)}>Cancel</Button>
          <Button
            variant="contained" color="success"
            onClick={() => approveId !== null && approveMut.mutate(approveId)}
            disabled={approveMut.isPending}
          >
            {approveMut.isPending ? 'Approving…' : 'Approve'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Reject dialog ──────────────────────────────────── */}
      <Dialog open={rejectId !== null} onClose={() => setRejectId(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Cancel color="error" />
          Reject Scorecard
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 1.5 }}>
            The scorecard will be returned to the maker for rework.
          </Alert>
          <TextField
            autoFocus required fullWidth multiline rows={3}
            label="Rejection reason *"
            value={rejectComments}
            onChange={(e) => setRejectComments(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectId(null)}>Cancel</Button>
          <Button
            variant="contained" color="error"
            onClick={() => rejectId !== null && rejectMut.mutate(rejectId)}
            disabled={rejectMut.isPending || !rejectComments.trim()}
          >
            {rejectMut.isPending ? 'Rejecting…' : 'Reject'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Submit dialog ──────────────────────────────────── */}
      <Dialog open={submitId !== null} onClose={() => setSubmitId(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Send color="primary" />
          Submit for Review
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth multiline rows={3}
            label="Notes for reviewer (optional)"
            value={submitNotes}
            onChange={(e) => setSubmitNotes(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSubmitId(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => submitId !== null && submitMut.mutate(submitId)}
            disabled={submitMut.isPending}
          >
            {submitMut.isPending ? 'Submitting…' : 'Submit'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
