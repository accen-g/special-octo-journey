import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Chip, Button, Paper, Tabs, Tab, Grid, Alert,
  TextField, CircularProgress, Divider,
} from '@mui/material';
import {
  ArrowBack as BackIcon, Download as DownloadIcon, CheckCircle,
  Cancel, Refresh as ReworkIcon, Lock as LockIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { kriOnboardingApi } from '../../api/client';
import { useAppSelector } from '../../store';
import type { KriBluesheetDetail, KriApprovalLogEntry } from '../../types';

const APPROVAL_STATUS_CFG: Record<string, { label: string; color: string; bg: string }> = {
  APPROVED:         { label: 'Approved',         color: '#2e7d32', bg: '#e8f5e9' },
  PENDING_APPROVAL: { label: 'Pending Approval',  color: '#e65100', bg: '#fff3e0' },
  REJECTED:         { label: 'Rejected',          color: '#c62828', bg: '#ffebee' },
  REWORK:           { label: 'Rework',            color: '#6a1e00', bg: '#fbe9e7' },
  DRAFT:            { label: 'Draft',             color: '#4527a0', bg: '#ede7f6' },
};

const SCORECARD_LABELS: [string, string][] = [
  ['sc_uk',           'UK Scorecard'],
  ['sc_finance',      'Finance Scorecard'],
  ['sc_risk',         'Risk Scorecard'],
  ['sc_liquidity',    'Liquidity Report Scorecards'],
  ['sc_capital',      'Capital Report Scorecards'],
  ['sc_risk_reports', 'Risk Reports Scorecard'],
  ['sc_markets',      'Markets Products Scorecard'],
];

function InfoField({ label, value }: { label: string; value?: string | null }) {
  return (
    <Box>
      <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#888', textTransform: 'uppercase', letterSpacing: 0.4, mb: 0.3 }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: '0.85rem', color: '#1a1a2e' }}>{value || '—'}</Typography>
    </Box>
  );
}

function TimelineItem({ action, name, dt, comment, status }: {
  action: string; name?: string; dt: string; comment?: string;
  status: 'done' | 'active' | 'wait';
}) {
  const dotStyle: Record<string, React.CSSProperties> = {
    done:   { background: '#e8f5e9', color: '#2e7d32', border: '2px solid #2e7d32' },
    active: { background: '#fff3e0', color: '#e65100', border: '2px solid #e65100' },
    wait:   { background: '#f5f5f5', color: '#bbb',    border: '2px solid #e0e0e0' },
  };
  const icon = status === 'done' ? '✓' : status === 'active' ? '⏳' : '·';
  return (
    <Box sx={{ display: 'flex', gap: 1.5, pb: 2.5, position: 'relative',
      '&:not(:last-child)::before': { content: '""', position: 'absolute', left: 13, top: 30, bottom: 0, width: 2, bgcolor: '#eee' }
    }}>
      <Box sx={{
        width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 12, fontWeight: 800, flexShrink: 0, mt: 0.3,
        ...dotStyle[status],
      }}>
        {icon}
      </Box>
      <Box sx={{ flex: 1 }}>
        <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: status === 'wait' ? '#bbb' : '#222' }}>{action}</Typography>
        {name && <Typography sx={{ fontSize: '0.75rem', color: '#888', mt: 0.3 }}>By {name} · {new Date(dt).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' })}</Typography>}
        {comment && (
          <Box sx={{ mt: 0.7, bgcolor: '#f5f5f5', borderRadius: 1, p: 0.8, fontSize: '0.78rem', color: '#555', fontStyle: 'italic' }}>
            "{comment}"
          </Box>
        )}
      </Box>
    </Box>
  );
}

export default function KriDetailPage() {
  const { kriId } = useParams<{ kriId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { user } = useAppSelector(s => s.auth);

  const [activeTab, setActiveTab] = useState(0);
  const [approvalComment, setApprovalComment] = useState('');
  const [actionError, setActionError] = useState('');

  // If navigated from listing with tab=approval, jump to approval tab
  useEffect(() => {
    if ((location.state as any)?.tab === 'approval') setActiveTab(5);
    if ((location.state as any)?.justSubmitted) setActiveTab(5);
  }, [location.state]);

  const { data: detail, isLoading, error } = useQuery<KriBluesheetDetail>({
    queryKey: ['kri-detail', kriId],
    queryFn: () => kriOnboardingApi.get(Number(kriId)).then(r => r.data),
    enabled: !!kriId,
  });

  const approveMutation = useMutation({
    mutationFn: ({ action, comments }: { action: string; comments?: string }) =>
      kriOnboardingApi.approve(Number(kriId), action, comments),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kri-detail', kriId] });
      qc.invalidateQueries({ queryKey: ['kri-onboarding-list'] });
      setApprovalComment('');
      setActionError('');
    },
    onError: (err: any) => {
      setActionError(err.response?.data?.detail || 'Action failed');
    },
  });

  const isL3 = user?.roles?.some(r => r.role_code === 'L3_ADMIN') ?? false;
  const isPending = detail?.approval_status === 'PENDING_APPROVAL' || detail?.approval_status === 'REWORK';

  const handleAction = (action: string) => {
    if (['REJECTED', 'REWORK'].includes(action) && !approvalComment.trim()) {
      setActionError('Comments are required when rejecting or requesting rework.');
      return;
    }
    setActionError('');
    approveMutation.mutate({ action, comments: approvalComment.trim() || undefined });
  };

  if (isLoading) return <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Box>;
  if (error || !detail) return (
    <Alert severity="error" sx={{ m: 2 }}>
      Failed to load KRI detail. <Button onClick={() => navigate('/kri-config')}>Go back</Button>
    </Alert>
  );

  const statusCfg = APPROVAL_STATUS_CFG[detail.approval_status] || APPROVAL_STATUS_CFG['DRAFT'];

  // Build approval timeline from log
  const logs: KriApprovalLogEntry[] = (detail as any).approval_log || [];

  return (
    <Box>
      {/* Breadcrumb */}
      <Box sx={{ display: 'flex', gap: 0.5, fontSize: '0.75rem', color: 'text.secondary', mb: 1.5 }}>
        <Typography
          component="span" sx={{ color: 'primary.main', fontWeight: 600, cursor: 'pointer', fontSize: '0.75rem' }}
          onClick={() => navigate('/kri-config')}
        >KRI Config</Typography>
        <Typography component="span" sx={{ fontSize: '0.75rem' }}>›</Typography>
        <Typography component="span" sx={{ fontSize: '0.75rem' }}>{detail.kri_code} — {detail.kri_name}</Typography>
      </Box>

      {/* Header strip */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: 20, fontWeight: 800, color: 'primary.main' }}>{detail.kri_code}</Typography>
              <Chip
                label={`● ${statusCfg.label}`}
                size="small"
                sx={{ bgcolor: statusCfg.bg, color: statusCfg.color, fontWeight: 700, fontSize: '0.72rem' }}
              />
            </Box>
            <Typography sx={{ fontSize: '0.9rem', fontWeight: 600, color: '#333', mt: 0.3 }}>{detail.kri_name}</Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button size="small" variant="outlined" startIcon={<DownloadIcon />}>Export PDF</Button>
            <Button size="small" variant="outlined" startIcon={<BackIcon />} onClick={() => navigate('/kri-config')}>
              Back to List
            </Button>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 2.5, mt: 1.5, flexWrap: 'wrap' }}>
          {[
            ['Category', detail.category_name],
            ['Region', detail.region_name],
            ['Risk Level', detail.risk_level],
            ['Version', '1.0'],
            ['Submitted By', detail.submitter_name],
            ['Submitted On', detail.submitted_dt ? new Date(detail.submitted_dt).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—'],
          ].map(([l, v]) => (
            <Box key={l}>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#888', textTransform: 'uppercase', letterSpacing: 0.4 }}>{l}</Typography>
              <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, color: '#1a1a2e' }}>{v || '—'}</Typography>
            </Box>
          ))}
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ overflow: 'hidden' }}>
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          sx={{ borderBottom: '2px solid #e5e5e5', px: 1.5, '& .MuiTab-root': { fontSize: '0.8rem', fontWeight: 600, minHeight: 44 } }}
        >
          <Tab label="Overview" />
          <Tab label="Roles & Owners" />
          <Tab label="Scorecard Coverage" />
          <Tab label="Rationale & Scope" />
          <Tab label="Runbook" />
          <Tab
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                Approval
                {isPending && <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#e65100' }} />}
              </Box>
            }
          />
        </Tabs>

        <Box sx={{ p: 2.5 }}>

          {/* Tab 0 — Overview */}
          {activeTab === 0 && (
            <Box>
              <Grid container spacing={2.5} sx={{ mb: 2 }}>
                <Grid item xs={6} sm={4}><InfoField label="KRI Code" value={detail.kri_code} /></Grid>
                <Grid item xs={6} sm={4}><InfoField label="Legacy ID" value={detail.legacy_kri_id} /></Grid>
                <Grid item xs={6} sm={4}><InfoField label="Threshold" value={detail.threshold} /></Grid>
                <Grid item xs={6} sm={4}><InfoField label="Circuit Breaker" value={detail.circuit_breaker} /></Grid>
                <Grid item xs={6} sm={4}><InfoField label="Frequency" value={detail.frequency} /></Grid>
                <Grid item xs={6} sm={4}><InfoField label="Control IDs" value={detail.control_ids} /></Grid>
              </Grid>
              <Divider sx={{ my: 2 }} />
              <InfoField label="Description" value={detail.description} />
              <Box sx={{ mt: 2 }}>
                <InfoField label="Data Quality Objectives" value={detail.dq_objectives} />
              </Box>
            </Box>
          )}

          {/* Tab 1 — Roles */}
          {activeTab === 1 && (
            <Box>
              {[
                ['Primary Senior Manager', detail.primary_senior_manager],
                ['Metric Owner', detail.metric_owner_name],
                ['Remediation Owner', detail.remediation_owner_name],
                ['B&I Metrics Lead', detail.bi_metrics_lead],
                ['Data Provider', detail.data_provider_name],
              ].map(([label, value]) => (
                <Box key={label} sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1.2, borderBottom: '1px solid #f2f2f2' }}>
                  <Typography sx={{ minWidth: 200, fontSize: '0.82rem', fontWeight: 600, color: '#333' }}>{label}</Typography>
                  <Typography sx={{ fontSize: '0.85rem' }}>{value || '—'}</Typography>
                </Box>
              ))}
            </Box>
          )}

          {/* Tab 2 — Scorecard Coverage */}
          {activeTab === 2 && (
            <Box>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>Scorecards this KRI contributes to:</Typography>
              <Grid container spacing={1}>
                {SCORECARD_LABELS.map(([key, label]) => (
                  <Grid item xs={6} key={key}>
                    <Box sx={{
                      display: 'flex', alignItems: 'center', gap: 1, p: 0.8,
                      border: '1px solid', borderColor: (detail as any)[key] ? 'primary.main' : '#e8e8e8',
                      borderRadius: 1, bgcolor: (detail as any)[key] ? '#e8eef5' : 'transparent',
                    }}>
                      <Box sx={{
                        width: 16, height: 16, borderRadius: 0.5, border: '1.5px solid',
                        borderColor: (detail as any)[key] ? 'primary.main' : '#ccc',
                        bgcolor: (detail as any)[key] ? 'primary.main' : 'transparent',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        {(detail as any)[key] && <Typography sx={{ color: '#fff', fontSize: 10, lineHeight: 1 }}>✓</Typography>}
                      </Box>
                      <Typography sx={{ fontSize: '0.82rem' }}>{label}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {/* Tab 3 — Rationale & Scope */}
          {activeTab === 3 && (
            <Grid container spacing={2.5}>
              <Grid item xs={12}><InfoField label="Why was this KRI selected?" value={detail.why_selected} /></Grid>
              <Divider sx={{ width: '100%', mx: 1.5 }} />
              <Grid item xs={12}><InfoField label="Rationale for threshold including global vs local approach, UK relevance, governance" value={detail.threshold_rationale} /></Grid>
              <Divider sx={{ width: '100%', mx: 1.5 }} />
              <Grid item xs={12}><InfoField label="Limitations and points for noting" value={detail.limitations} /></Grid>
              <Divider sx={{ width: '100%', mx: 1.5 }} />
              <Grid item xs={12}><InfoField label="KRI Calculation and Scope" value={detail.kri_calculation} /></Grid>
            </Grid>
          )}

          {/* Tab 4 — Runbook */}
          {activeTab === 4 && (
            <Box>
              <Alert severity="info" sx={{ mb: 2, fontSize: '0.78rem' }}>
                Runbooks are stored in S3 at <code>s3://bic-kri-runbooks/{detail.region_name?.toLowerCase() || 'uk'}/{detail.kri_code}/</code>. Click the filename to download.
              </Alert>
              {detail.runbook_filename ? (
                <Box sx={{
                  display: 'flex', alignItems: 'center', gap: 1.5, maxWidth: 480,
                  border: '1px solid #d5d5d5', borderRadius: 1.5, p: 1.5, cursor: 'pointer',
                  '&:hover': { bgcolor: '#f4f7fb' },
                }}>
                  <Typography sx={{ fontSize: 24 }}>📕</Typography>
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'primary.main' }}>{detail.runbook_filename}</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      Version: {detail.runbook_version || '—'}
                      {detail.runbook_review_date ? ` · Last reviewed: ${new Date(detail.runbook_review_date).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})}` : ''}
                    </Typography>
                  </Box>
                  <DownloadIcon sx={{ color: 'primary.main' }} />
                </Box>
              ) : (
                <Typography sx={{ color: 'text.secondary', fontStyle: 'italic' }}>No runbook uploaded.</Typography>
              )}
              {detail.runbook_notes && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>Notes:</Typography>
                  <Typography variant="body2" sx={{ mt: 0.3 }}>{detail.runbook_notes}</Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Tab 5 — Approval */}
          {activeTab === 5 && (
            <Box>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'primary.main', textTransform: 'uppercase', letterSpacing: .5, mb: 1.5 }}>
                Approval History
              </Typography>

              {/* Timeline */}
              <Box sx={{ mb: 2 }}>
                {logs.length === 0 ? (
                  <TimelineItem action="Not yet submitted" name={undefined} dt={new Date().toISOString()} comment={undefined} status="wait" />
                ) : (
                  logs.map((log, i) => (
                    <TimelineItem
                      key={log.log_id}
                      action={
                        log.action === 'SUBMITTED' ? 'KRI Submitted' :
                        log.action === 'APPROVED' ? 'L3 Approved — KRI is now Active' :
                        log.action === 'REJECTED' ? 'L3 Rejected' :
                        'Rework Requested'
                      }
                      name={log.performer_name || `User #${log.performed_by}`}
                      dt={log.performed_dt}
                      comment={log.comments}
                      status={
                        log.action === 'SUBMITTED' ? 'done' :
                        log.action === 'APPROVED' ? 'done' : 'done'
                      }
                    />
                  ))
                )}
                {/* Pending awaiting step */}
                {detail.approval_status === 'PENDING_APPROVAL' && (
                  <TimelineItem action="L3 Review — Awaiting Decision" name={undefined} dt={new Date().toISOString()} comment={undefined} status="active" />
                )}
                {detail.approval_status === 'APPROVED' && (
                  <TimelineItem action="KRI Active — Visible in Data Control" name={undefined} dt={new Date().toISOString()} comment={undefined} status="done" />
                )}
              </Box>

              {/* L3 action box — only for L3 on pending/rework KRIs */}
              {isPending && isL3 && (
                <Box sx={{ border: '2px solid', borderColor: 'primary.main', borderRadius: 2, p: 2, bgcolor: '#f8fafd' }}>
                  <Typography sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                    🔐 Your Action — {user?.full_name} (L3 Admin)
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
                    Review all tabs above (Runbook, Roles, Rationale) before deciding. Your action will be permanently logged with a timestamp.
                  </Typography>
                  {actionError && <Alert severity="error" sx={{ mb: 1.5, fontSize: '0.78rem' }}>{actionError}</Alert>}
                  {approveMutation.isError && !actionError && (
                    <Alert severity="error" sx={{ mb: 1.5, fontSize: '0.78rem' }}>Action failed. Please try again.</Alert>
                  )}
                  <TextField
                    fullWidth multiline rows={3} size="small"
                    placeholder="Review comments — required when Rejecting or requesting Rework…"
                    value={approvalComment}
                    onChange={e => setApprovalComment(e.target.value)}
                    sx={{ mb: 1.5 }}
                  />
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Button
                      variant="contained" color="success"
                      startIcon={approveMutation.isPending ? <CircularProgress size={14} color="inherit" /> : <CheckCircle />}
                      disabled={approveMutation.isPending}
                      onClick={() => handleAction('APPROVED')}
                    >
                      Approve KRI
                    </Button>
                    <Button
                      variant="contained" color="warning"
                      startIcon={<ReworkIcon />}
                      disabled={approveMutation.isPending}
                      onClick={() => handleAction('REWORK')}
                    >
                      Request Rework
                    </Button>
                    <Button
                      variant="contained" color="error"
                      startIcon={<Cancel />}
                      disabled={approveMutation.isPending}
                      onClick={() => handleAction('REJECTED')}
                    >
                      Reject KRI
                    </Button>
                    <Typography variant="caption" sx={{ ml: 'auto', color: 'text.secondary' }}>
                      Logged as: {user?.full_name} · L3 Admin
                    </Typography>
                  </Box>
                </Box>
              )}

              {/* Lock notice for non-L3 on pending KRIs */}
              {isPending && !isL3 && (
                <Box sx={{ border: '1.5px dashed #ccc', borderRadius: 2, p: 2, bgcolor: '#f8f9fa' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.8 }}>
                    <LockIcon sx={{ fontSize: 18, color: '#888' }} />
                    <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#555' }}>Approval Access Restricted</Typography>
                  </Box>
                  <Typography variant="body2" sx={{ color: '#888' }}>
                    Only users with the <strong>L3 Admin</strong> role can approve, reject, or request rework on KRI submissions.
                    You are logged in as <strong>{user?.full_name}</strong>.
                    Contact a user with the L3 Admin role to perform approval actions.
                  </Typography>
                </Box>
              )}

              {/* Read-only completed state for non-pending */}
              {!isPending && detail.approval_status !== 'DRAFT' && (
                <Alert
                  severity={detail.approval_status === 'APPROVED' ? 'success' : 'warning'}
                  sx={{ mt: 1 }}
                >
                  This KRI has been <strong>{detail.approval_status.toLowerCase()}</strong>. No further action required.
                </Alert>
              )}
            </Box>
          )}

        </Box>
      </Paper>
    </Box>
  );
}
