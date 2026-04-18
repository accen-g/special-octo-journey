/**
 * Audit Evidence Page — replaces the old Evidence Vault.
 *
 * Layout:
 *   StatCards → KRI table (with evidence count pill) → UploadEvidenceModal + ViewEvidenceModal
 */
import React, { useCallback, useRef, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress,
  Dialog, DialogActions, DialogContent, DialogTitle,
  Grid, IconButton, LinearProgress, Tab, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Tabs,
  TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography,
} from '@mui/material';
import {
  CloudUpload, Visibility, Assignment, Email, CheckCircle,
  HourglassEmpty, Search, Download,
} from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { auditEvidenceApi } from '../../api/client';
import { useAppSelector } from '../../store';
import { hasRole } from '../../utils/helpers';
import type { AuditEvidenceItem, AuditEvidenceKriRow, AuditSummary } from '../../types';
import TableHeaderFilters from '../../components/common/TableHeaderFilters';

// ─── Helpers ────────────────────────────────────────────────
const MONTHS = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function periodLabel(year: number, month: number) {
  return `${MONTHS[month] ?? month} ${year}`;
}

function statusChip(status: string) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    APPROVED:          { label: 'Approved',      color: '#065f46', bg: '#d1fae5' },
    PENDING_APPROVAL:  { label: 'Pending',        color: '#92400e', bg: '#fef3c7' },
    IN_PROGRESS:       { label: 'In Progress',    color: '#1e40af', bg: '#dbeafe' },
    REWORK:            { label: 'Rework',          color: '#9a3412', bg: '#ffedd5' },
    SLA_BREACHED:      { label: 'SLA Breached',   color: '#991b1b', bg: '#fee2e2' },
    NOT_STARTED:       { label: 'Not Started',    color: '#374151', bg: '#f3f4f6' },
  };
  const s = map[status] ?? { label: status, color: '#374151', bg: '#f3f4f6' };
  return (
    <Chip
      label={s.label}
      size="small"
      sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, fontSize: '0.7rem' }}
    />
  );
}

function evidenceTypeBadge(type: string) {
  const colors: Record<string, string> = { manual: '#1e40af', auto: '#065f46', email: '#6b21a8' };
  return (
    <Chip
      label={type.charAt(0).toUpperCase() + type.slice(1)}
      size="small"
      sx={{ bgcolor: '#f3f4f6', color: colors[type] ?? '#374151', fontWeight: 600, fontSize: '0.68rem' }}
    />
  );
}

// ─── Upload Evidence Modal ───────────────────────────────────
interface UploadKriContext {
  kri_id: number;
  kri_code?: string;
  kri_name: string;
  region_code?: string;
  region_name?: string;
  dimension_id: number;      // which control this upload targets
  control_id?: string;       // dimension_code for S3 path
  control_name?: string;     // human-readable control name for display
  period_year: number;
  period_month: number;
}

interface UploadEvidenceModalProps {
  open: boolean;
  onClose: () => void;
  kri: UploadKriContext | null;
}

function UploadEvidenceModal({ open, onClose, kri }: UploadEvidenceModalProps) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [notes, setNotes] = useState('');
  const [evidenceType, setEvidenceType] = useState<'manual' | 'auto'>('manual');
  const [fileError, setFileError] = useState(false);

  const reset = useCallback(() => {
    setSelectedFile(null);
    setNotes('');
    setEvidenceType('manual');
    setFileError(false);
  }, []);

  const handleClose = () => { reset(); onClose(); };

  const uploadMutation = useMutation({
    mutationFn: (fd: FormData) => auditEvidenceApi.upload(fd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-evidence-kris'] });
      queryClient.invalidateQueries({ queryKey: ['audit-evidence'] });
      handleClose();
    },
  });

  const handleSubmit = () => {
    if (!selectedFile) { setFileError(true); return; }
    if (!kri) return;
    const fd = new FormData();
    fd.append('file', selectedFile);
    fd.append('kri_id', String(kri.kri_id));
    fd.append('year', String(kri.period_year));
    fd.append('month', String(kri.period_month));
    fd.append('evidence_type', evidenceType);
    fd.append('dimension_id', String(kri.dimension_id));
    if (notes) fd.append('notes', notes);
    uploadMutation.mutate(fd);
  };

  const s3PathPreview = kri
    ? `BIC/KRI/${kri.region_code ?? '?'}/${kri.period_year}/${String(kri.period_month).padStart(2, '0')}/Evidences/TEMP/${kri.control_id ?? 'COMMON'}/COMMON/`
    : '';

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1 }}>
        <CloudUpload fontSize="small" /> Upload Evidence
        {kri && (
          <Typography variant="body2" sx={{ color: 'text.secondary', ml: 1, fontWeight: 400 }}>
            {kri.kri_code} &nbsp;|&nbsp; {kri.control_name ?? kri.control_id ?? '—'} &nbsp;|&nbsp; {periodLabel(kri.period_year, kri.period_month)} &nbsp;|&nbsp; {kri.region_name ?? kri.region_code}
          </Typography>
        )}
      </DialogTitle>

      <DialogContent dividers>
        {kri && (
          <>
            {/* KRI Context (read-only) */}
            <Grid container spacing={1.5} sx={{ mb: 2 }}>
              <Grid item xs={4}>
                <Typography variant="caption" color="text.secondary">KRI ID</Typography>
                <Typography variant="body2" fontWeight={700}>KRI-{kri.kri_id}</Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="caption" color="text.secondary">Region</Typography>
                <Typography variant="body2">{kri.region_name ?? kri.region_code ?? '—'}</Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="caption" color="text.secondary">Period</Typography>
                <Typography variant="body2">{periodLabel(kri.period_year, kri.period_month)}</Typography>
              </Grid>
              <Grid item xs={8}>
                <Typography variant="caption" color="text.secondary">KRI Name</Typography>
                <Typography variant="body2">{kri.kri_name}</Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="caption" color="text.secondary">Control</Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                  {kri.control_name ?? kri.control_id ?? '—'}
                </Typography>
              </Grid>
            </Grid>

            {/* S3 path preview */}
            <Box sx={{ bgcolor: '#1e293b', color: '#94a3b8', borderRadius: 1, px: 2, py: 1, mb: 2, fontFamily: 'monospace', fontSize: '0.72rem', wordBreak: 'break-all' }}>
              {s3PathPreview}
            </Box>

            {/* Evidence Type toggle */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>Evidence Type</Typography>
              <ToggleButtonGroup
                exclusive
                value={evidenceType}
                onChange={(_, v) => { if (v) setEvidenceType(v); }}
                size="small"
              >
                <ToggleButton value="manual">Manual</ToggleButton>
                <ToggleButton value="auto">Auto</ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {/* Drop zone */}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.xlsx,.png,.eml,.msg,.docx,.csv,.pptx"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setSelectedFile(f);
                setFileError(!f);
              }}
            />
            <Box
              onClick={() => fileRef.current?.click()}
              sx={{
                border: fileError ? '2px solid #ef4444' : '2px dashed #94a3b8',
                borderRadius: 2,
                p: 3,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: fileError ? '#fef2f2' : '#f8fafc',
                mb: 2,
                transition: 'border-color 0.2s',
                '&:hover': { borderColor: '#1a56db' },
              }}
            >
              <CloudUpload sx={{ fontSize: 36, color: '#94a3b8', mb: 1 }} />
              <Typography variant="body2" color="text.secondary">
                {selectedFile ? selectedFile.name : 'Drag & drop or click to browse'}
              </Typography>
              <Typography variant="caption" color="text.disabled">
                PDF, XLSX, PNG, EML · max 25 MB
              </Typography>
            </Box>
            {fileError && (
              <Alert severity="error" sx={{ mb: 2, py: 0 }}>A file is required before uploading.</Alert>
            )}

            {/* Notes */}
            <TextField
              label="Notes (optional)"
              multiline
              rows={2}
              fullWidth
              size="small"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </>
        )}

        {uploadMutation.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            Upload failed. Please try again.
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={uploadMutation.isPending}>Cancel</Button>
        <Button
          variant="contained"
          startIcon={uploadMutation.isPending ? <CircularProgress size={14} /> : <CloudUpload />}
          onClick={handleSubmit}
          disabled={uploadMutation.isPending}
        >
          {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── View Evidence Modal ─────────────────────────────────────
interface ViewEvidenceModalProps {
  open: boolean;
  onClose: () => void;
  kriId: number | null;
  kriCode?: string;
  kriName?: string;
  controlCode?: string;   // dimension_code — filters evidence to this control only
  controlName?: string;   // for display
  periodYear: number;
  periodMonth: number;
  approvalStatus?: string; // MonthlyControlStatus.status — gates audit summary generation
}

function ViewEvidenceModal({ open, onClose, kriId, kriCode, kriName, controlCode, controlName, periodYear, periodMonth, approvalStatus }: ViewEvidenceModalProps) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'all' | 'email' | 'audit'>('all');
  const { user } = useAppSelector((s) => s.auth);
  const isL3 = user?.roles?.some(r => r.role_code === 'L3_ADMIN' || r.role_code === 'SYSTEM_ADMIN') ?? false;

  // DEBUG — remove after confirming regenerate button fix
  console.log('[EvidenceModal] kriCode:', kriCode, '| isL3:', isL3, '| approvalStatus:', approvalStatus, '| showRegenerate:', isL3 && approvalStatus === 'APPROVED');

  const { data: evidences = [], isLoading } = useQuery<AuditEvidenceItem[]>({
    queryKey: ['audit-evidence', kriId, periodYear, periodMonth, controlCode],
    queryFn: () =>
      auditEvidenceApi.list({
        kri_id: kriId,
        year: periodYear,
        month: periodMonth,
        ...(controlCode ? { control_code: controlCode } : {}),
      }).then(r => r.data),
    enabled: open && kriId !== null,
  });

  const { data: summary } = useQuery<AuditSummary>({
    queryKey: ['audit-summary', kriId, periodYear, periodMonth],
    queryFn: () =>
      auditEvidenceApi.getSummary(kriId!, { year: periodYear, month: periodMonth }).then(r => r.data),
    enabled: open && kriId !== null && tab === 'audit',
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: () => auditEvidenceApi.generateSummary(kriId!, { year: periodYear, month: periodMonth, control_code: controlCode }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-summary', kriId, periodYear, periodMonth] });
    },
  });

  const [presignedUrls, setPresignedUrls] = useState<Record<number, string>>({});
  const fetchUrl = async (ev: AuditEvidenceItem) => {
    if (presignedUrls[ev.evidence_id]) return;
    try {
      const r = await auditEvidenceApi.presignedUrl(ev.kri_id, ev.evidence_id);
      setPresignedUrls(prev => ({ ...prev, [ev.evidence_id]: r.data.url }));
    } catch {
      // ignore
    }
  };

  const totalCount = evidences.length;
  const emailCount = evidences.filter(e => e.evidence_type === 'email').length;
  const manualCount = evidences.filter(e => e.evidence_type === 'manual').length;
  const iterations = new Set(evidences.filter(e => e.iteration).map(e => e.iteration)).size;

  // Group email evidence by iteration
  const emailByIter: Record<number, AuditEvidenceItem[]> = {};
  evidences.filter(e => e.evidence_type === 'email').forEach(e => {
    const it = e.iteration ?? 0;
    if (!emailByIter[it]) emailByIter[it] = [];
    emailByIter[it].push(e);
  });

  const fmtDt = (dt?: string) => {
    if (!dt) return '—';
    return new Date(dt).toLocaleString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Visibility fontSize="small" /> Evidence — {kriCode}
        <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 400, ml: 1 }}>
          {kriName}
          {controlName && <> &nbsp;|&nbsp; <strong>{controlName}</strong></>}
          &nbsp;|&nbsp; {periodLabel(periodYear, periodMonth)}
        </Typography>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        {isLoading ? (
          <LinearProgress />
        ) : (
          <>
            {/* Summary stat chips */}
            <Box sx={{ display: 'flex', gap: 1, px: 2, pt: 2, pb: 1, flexWrap: 'wrap' }}>
              <Chip label={`${totalCount} Total`} size="small" color="primary" variant="outlined" />
              <Chip label={`${iterations} Iterations`} size="small" variant="outlined" />
              <Chip label={`${emailCount} Emails`} size="small" variant="outlined" sx={{ color: '#6b21a8', borderColor: '#6b21a8' }} />
              <Chip label={`${manualCount} Manual`} size="small" variant="outlined" sx={{ color: '#1e40af', borderColor: '#1e40af' }} />
            </Box>

            <Tabs
              value={tab}
              onChange={(_, v) => setTab(v)}
              sx={{ px: 2, borderBottom: '1px solid', borderColor: 'divider' }}
            >
              <Tab label={`All Evidence (${totalCount})`} value="all" />
              <Tab label={`Email Trail (${emailCount})`} value="email" />
              <Tab label="Audit Summary" value="audit" />
            </Tabs>

            {/* All Evidence */}
            {tab === 'all' && (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>File Name</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Type</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Action</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>By</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Time</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }} align="center">View</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {evidences.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6}>
                          <Alert severity="info" sx={{ m: 1 }}>No evidence files yet.</Alert>
                        </TableCell>
                      </TableRow>
                    ) : evidences.map((ev) => (
                      <TableRow key={ev.evidence_id} hover>
                        <TableCell sx={{ fontSize: '0.78rem' }}>{ev.file_name}</TableCell>
                        <TableCell>{evidenceTypeBadge(ev.evidence_type)}</TableCell>
                        <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{ev.action ?? '—'}</TableCell>
                        <TableCell sx={{ fontSize: '0.75rem' }}>{ev.uploaded_by_name ?? 'SYSTEM'}</TableCell>
                        <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>{fmtDt(ev.created_dt)}</TableCell>
                        <TableCell align="center">
                          <Tooltip title="View / Download">
                            <IconButton
                              size="small"
                              onClick={() => fetchUrl(ev).then(() => {
                                const url = presignedUrls[ev.evidence_id];
                                if (url) window.open(url, '_blank');
                              })}
                            >
                              <Visibility fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Email Trail */}
            {tab === 'email' && (
              <Box sx={{ p: 2 }}>
                {Object.keys(emailByIter).length === 0 ? (
                  <Alert severity="info">No email trail recorded for this period.</Alert>
                ) : Object.entries(emailByIter).sort(([a], [b]) => Number(a) - Number(b)).map(([iter, emails]) => (
                  <Box key={iter} sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, color: '#1e40af' }}>
                      Iteration {iter}
                    </Typography>
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Direction</TableCell>
                            <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>File / Subject</TableCell>
                            <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>From</TableCell>
                            <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>To</TableCell>
                            <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Timestamp</TableCell>
                            <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Download</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {emails.map((ev) => (
                            <TableRow key={ev.evidence_id} hover>
                              <TableCell>
                                <Chip
                                  label={ev.action === 'INBOUND' ? '↙ Inbound' : '↗ Outgoing'}
                                  size="small"
                                  sx={{
                                    bgcolor: ev.action === 'INBOUND' ? '#f0fdf4' : '#eff6ff',
                                    color: ev.action === 'INBOUND' ? '#166534' : '#1e40af',
                                    fontWeight: 600, fontSize: '0.68rem',
                                  }}
                                />
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.78rem' }}>{ev.file_name}</TableCell>
                              <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{ev.sender ?? '—'}</TableCell>
                              <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{ev.receiver ?? '—'}</TableCell>
                              <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>{fmtDt(ev.created_dt)}</TableCell>
                              <TableCell>
                                <IconButton
                                  size="small"
                                  onClick={() => fetchUrl(ev).then(() => {
                                    const url = presignedUrls[ev.evidence_id];
                                    if (url) window.open(url, '_blank');
                                  })}
                                  title="Download .eml"
                                >
                                  <Download fontSize="small" />
                                </IconButton>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                ))}
              </Box>
            )}

            {/* Audit Summary */}
            {tab === 'audit' && (
              <Box sx={{ p: 2 }}>
                {summary ? (
                  <Box>
                    <Alert severity="success" icon={<CheckCircle />} sx={{ mb: 2 }}>
                      Audit summary generated on {fmtDt(summary.generated_dt)} by {summary.l3_approver_name ?? 'L3 Approver'}.
                    </Alert>
                    <Grid container spacing={2}>
                      <Grid item xs={4}>
                        <Box sx={{ border: '1px solid #e5e7eb', borderRadius: 2, p: 2, textAlign: 'center' }}>
                          <Typography sx={{ fontSize: 28, fontWeight: 700, color: '#1a56db' }}>{summary.total_iterations}</Typography>
                          <Typography variant="caption" color="text.secondary">Iterations</Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={4}>
                        <Box sx={{ border: '1px solid #e5e7eb', borderRadius: 2, p: 2, textAlign: 'center' }}>
                          <Typography sx={{ fontSize: 28, fontWeight: 700, color: '#1a56db' }}>{summary.total_evidences}</Typography>
                          <Typography variant="caption" color="text.secondary">Evidence Files</Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={4}>
                        <Box sx={{ border: '1px solid #e5e7eb', borderRadius: 2, p: 2, textAlign: 'center' }}>
                          <Typography sx={{ fontSize: 28, fontWeight: 700, color: '#6b21a8' }}>{summary.total_emails}</Typography>
                          <Typography variant="caption" color="text.secondary">Email Exchanges</Typography>
                        </Box>
                      </Grid>
                    </Grid>
                    <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                      <Button
                        variant="outlined"
                        startIcon={<Download />}
                        onClick={() => window.open(_generate_presigned_url_client(summary.s3_path), '_blank')}
                      >
                        Download summary.html
                      </Button>
                      {isL3 && approvalStatus === 'APPROVED' && (
                        <Button
                          variant="outlined"
                          color="warning"
                          startIcon={generateMutation.isPending ? <CircularProgress size={14} /> : <Assignment />}
                          onClick={() => generateMutation.mutate()}
                          disabled={generateMutation.isPending}
                        >
                          {generateMutation.isPending ? 'Regenerating…' : 'Regenerate Summary'}
                        </Button>
                      )}
                    </Box>
                  </Box>
                ) : (
                  <Box>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      No audit summary generated yet for this period.
                    </Alert>
                    {isL3 && approvalStatus === 'APPROVED' && (
                      <Button
                        variant="contained"
                        startIcon={generateMutation.isPending ? <CircularProgress size={14} /> : <Assignment />}
                        onClick={() => generateMutation.mutate()}
                        disabled={generateMutation.isPending}
                      >
                        {generateMutation.isPending ? 'Generating…' : 'Generate Audit Summary'}
                      </Button>
                    )}
                    {isL3 && approvalStatus !== 'APPROVED' && (
                      <Typography variant="body2" color="text.secondary">
                        Audit summary can only be generated after final L3 approval.
                      </Typography>
                    )}
                    {!isL3 && (
                      <Typography variant="body2" color="text.secondary">
                        Only L3 Admins can generate the audit summary.
                      </Typography>
                    )}
                    {generateMutation.isError && (
                      <Alert severity="error" sx={{ mt: 1 }}>Failed to generate summary.</Alert>
                    )}
                  </Box>
                )}
              </Box>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

/** Dev helper — constructs a download URL for the local-fallback presigned path */
function _generate_presigned_url_client(s3Path: string): string {
  return `/api/audit-evidence/local-download?key=${encodeURIComponent(s3Path)}`;
}

// ─── Main Evidence Page ──────────────────────────────────────
export default function EvidencePage() {
  const { user } = useAppSelector((s) => s.auth);
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [colFilters, setColFilters] = useState({
    kri_code: '', kri_name: '', region: '', control_id: '', data_provider: '',
  });

  // Upload modal state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadKri, setUploadKri] = useState<UploadKriContext | null>(null);

  // View modal state
  const [viewOpen, setViewOpen] = useState(false);
  const [viewKri, setViewKri] = useState<AuditEvidenceKriRow | null>(null);

  const canUpload = hasRole(user?.roles || [], [
    'L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'DATA_PROVIDER', 'SYSTEM_ADMIN',
  ]);

  const { data: kris = [], isLoading } = useQuery<AuditEvidenceKriRow[]>({
    queryKey: ['audit-evidence-kris', selectedPeriod, selectedRegionId],
    queryFn: () =>
      auditEvidenceApi
        .listKris({
          year: selectedPeriod.year,
          month: selectedPeriod.month,
          region_id: selectedRegionId || undefined,
        })
        .then(r => r.data),
  });

  // Derived stat counts — each entry is one KRI × Control combination
  const totalKris = kris.length;
  const withEvidence = kris.filter(k => k.evidence_count > 0).length;
  const pending = kris.filter(k => k.status === 'PENDING_APPROVAL').length;
  const approved = kris.filter(k => k.status === 'APPROVED').length;

  // Client-side search + status + column filters
  const filtered = kris.filter(k => {
    const q = search.toLowerCase();
    if (q && !k.kri_code?.toLowerCase().includes(q) && !k.kri_name.toLowerCase().includes(q)) return false;
    if (statusFilter && k.status !== statusFilter) return false;
    if (colFilters.kri_code && !k.kri_code?.toLowerCase().includes(colFilters.kri_code.toLowerCase())) return false;
    if (colFilters.kri_name && !k.kri_name.toLowerCase().includes(colFilters.kri_name.toLowerCase())) return false;
    if (colFilters.region && !(k.region_name ?? k.region_code ?? '').toLowerCase().includes(colFilters.region.toLowerCase())) return false;
    if (colFilters.control_id && !(
      (k.control_name ?? '').toLowerCase().includes(colFilters.control_id.toLowerCase()) ||
      (k.control_id ?? '').toLowerCase().includes(colFilters.control_id.toLowerCase())
    )) return false;
    if (colFilters.data_provider && !(k.data_provider_name ?? '').toLowerCase().includes(colFilters.data_provider.toLowerCase())) return false;
    return true;
  });

  const openUpload = (row: AuditEvidenceKriRow) => {
    setUploadKri({
      kri_id: row.kri_id,
      kri_code: row.kri_code,
      kri_name: row.kri_name,
      region_code: row.region_code,
      region_name: row.region_name,
      dimension_id: row.dimension_id,
      control_id: row.control_id,
      control_name: row.control_name,
      period_year: row.period_year,
      period_month: row.period_month,
    });
    setUploadOpen(true);
  };

  const openView = (row: AuditEvidenceKriRow) => {
    setViewKri(row);
    setViewOpen(true);
  };

  const STATUS_FILTERS = [
    { label: 'All', value: null },
    { label: 'Pending', value: 'PENDING_APPROVAL' },
    { label: 'Approved', value: 'APPROVED' },
    { label: 'In Progress', value: 'IN_PROGRESS' },
    { label: 'Rework', value: 'REWORK' },
  ];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Audit Evidence
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {periodLabel(selectedPeriod.year, selectedPeriod.month)}
        </Typography>
      </Box>

      {/* Stat Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { label: 'Total Controls', value: totalKris, color: '#1a56db', icon: <Assignment /> },
          { label: 'With Evidence', value: withEvidence, color: '#065f46', icon: <CheckCircle /> },
          { label: 'Pending Approval', value: pending, color: '#92400e', icon: <HourglassEmpty /> },
          { label: 'Approved', value: approved, color: '#065f46', icon: <CheckCircle /> },
        ].map((card) => (
          <Grid item xs={6} sm={3} key={card.label}>
            <Card elevation={0} sx={{ border: '1px solid #e5e7eb', borderRadius: 2 }}>
              <CardContent sx={{ py: 1.5 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography sx={{ fontSize: 26, fontWeight: 700, color: card.color, lineHeight: 1 }}>
                      {card.value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">{card.label}</Typography>
                  </Box>
                  <Box sx={{ color: card.color, opacity: 0.3 }}>{card.icon}</Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Toolbar: search + status chips */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder="Search KRI code or name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{ startAdornment: <Search fontSize="small" sx={{ mr: 0.5, color: 'text.disabled' }} /> }}
          sx={{ minWidth: 260 }}
        />
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {STATUS_FILTERS.map(f => (
            <Chip
              key={f.label}
              label={f.label}
              clickable
              onClick={() => setStatusFilter(f.value)}
              variant={statusFilter === f.value ? 'filled' : 'outlined'}
              color={statusFilter === f.value ? 'primary' : 'default'}
              size="small"
            />
          ))}
        </Box>
      </Box>

      {/* KRI Table */}
      <Card elevation={0} sx={{ border: '1px solid #e5e7eb', borderRadius: 2 }}>
        <CardContent sx={{ p: 0 }}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}>
              <CircularProgress />
            </Box>
          ) : filtered.length === 0 ? (
            <Alert severity="info" sx={{ m: 2 }}>
              No KRIs found for the selected period and filters.
            </Alert>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {['KRI Code','KRI Name','Control ID','Region','Data Provider','Status','Evidence','Actions'].map(h => (
                      <TableCell key={h} sx={{ whiteSpace: 'nowrap', fontSize: '0.72rem' }}>
                        {h}
                      </TableCell>
                    ))}
                  </TableRow>
                  {/* Inline column filters — shared component (matches Approvals page pattern) */}
                  <TableHeaderFilters
                    filters={[
                      { key: 'kri_code', label: 'KRI Code', type: 'text',
                        value: colFilters.kri_code, onChange: (v) => setColFilters(p => ({ ...p, kri_code: v })) },
                      { key: 'kri_name', label: 'KRI Name', type: 'text',
                        value: colFilters.kri_name, onChange: (v) => setColFilters(p => ({ ...p, kri_name: v })) },
                      { key: 'control_id', label: 'Control ID', type: 'text',
                        value: colFilters.control_id, onChange: (v) => setColFilters(p => ({ ...p, control_id: v })) },
                      { key: 'region', label: 'Region', type: 'text',
                        value: colFilters.region, onChange: (v) => setColFilters(p => ({ ...p, region: v })) },
                      { key: 'data_provider', label: 'Data Provider', type: 'text',
                        value: colFilters.data_provider, onChange: (v) => setColFilters(p => ({ ...p, data_provider: v })) },
                      { key: '_status', label: '', type: 'none', value: '', onChange: () => {} },
                      { key: '_evidence', label: '', type: 'none', value: '', onChange: () => {} },
                      { key: '_actions', label: '', type: 'none', value: '', onChange: () => {} },
                    ]}
                  />
                </TableHead>
                <TableBody>
                  {filtered.map((row) => (
                    <TableRow key={`${row.kri_id}-${row.dimension_id}`} hover>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.8rem' }}>
                          {row.kri_code ?? `KRI-${row.kri_id}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontSize: '0.82rem' }}>
                          {row.kri_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontSize: '0.78rem', fontWeight: 600, color: row.control_name ? '#1e40af' : 'text.disabled' }}>
                          {row.control_name ?? row.control_id ?? '—'}
                        </Typography>
                        {row.control_id && row.control_name && (
                          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.disabled', fontSize: '0.68rem', display: 'block' }}>
                            {row.control_id}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontSize: '0.78rem' }}>
                          {row.region_name ?? row.region_code ?? '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
                          {row.data_provider_name ?? '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>{statusChip(row.status)}</TableCell>
                      <TableCell align="center">
                        {row.evidence_count > 0 ? (
                          <Chip
                            label={row.evidence_count}
                            size="small"
                            clickable
                            onClick={() => openView(row)}
                            sx={{
                              bgcolor: '#dbeafe',
                              color: '#1e40af',
                              fontWeight: 700,
                              minWidth: 32,
                              cursor: 'pointer',
                              '&:hover': { bgcolor: '#bfdbfe' },
                            }}
                          />
                        ) : (
                          <Typography variant="caption" color="text.disabled">—</Typography>
                        )}
                      </TableCell>
                      <TableCell align="center">
                        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.4, alignItems: 'center', flexWrap: 'nowrap' }}>
                          {canUpload && (
                            <Tooltip title="Upload Evidence">
                              <IconButton
                                size="small"
                                onClick={() => openUpload(row)}
                                sx={{ border: '1px solid', borderColor: 'primary.light', borderRadius: 1.5, p: 0.5 }}
                              >
                                <CloudUpload fontSize="small" sx={{ color: '#1a56db' }} />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Tooltip title="View Evidence">
                            <IconButton
                              size="small"
                              onClick={() => openView(row)}
                              sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1.5, p: 0.5 }}
                            >
                              <Visibility fontSize="small" sx={{ color: '#374151' }} />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <UploadEvidenceModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        kri={uploadKri}
      />

      {viewKri && (
        <ViewEvidenceModal
          open={viewOpen}
          onClose={() => setViewOpen(false)}
          kriId={viewKri.kri_id}
          kriCode={viewKri.kri_code}
          kriName={viewKri.kri_name}
          controlCode={viewKri.control_id}
          controlName={viewKri.control_name}
          periodYear={viewKri.period_year}
          periodMonth={viewKri.period_month}
          approvalStatus={viewKri.maker_checker_status}
        />
      )}
    </Box>
  );
}
