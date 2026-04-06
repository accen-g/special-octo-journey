import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, Tabs, Tab, Button, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Select, MenuItem, FormControl, InputLabel,
  Collapse, IconButton, Tooltip,
} from '@mui/material';
import {
  CheckCircle, Cancel, Replay, ArrowForward, KeyboardArrowDown,
  KeyboardArrowUp, Folder, Comment, History,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { makerCheckerApi, userApi, commentApi, controlApi } from '../../api/client';
import { useAppSelector } from '../../store';
import { hasRole, isL3Admin } from '../../utils/helpers';

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

  // Approver summary row
  const approverRows = [
    { level: 'L1', name: item.l1_approver_name, id: item.l1_approver_id, action: item.l1_action },
    { level: 'L2', name: item.l2_approver_name, id: item.l2_approver_id, action: item.l2_action },
    { level: 'L3', name: item.l3_approver_name, id: item.l3_approver_id, action: item.l3_action },
  ].filter((r) => r.id);

  return (
    <Box sx={{ px: 3, py: 2, bgcolor: '#fafafa', borderTop: '1px solid', borderColor: 'divider' }}>
      {/* Approver assignment summary */}
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

      {/* Audit trail table */}
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


export default function ApprovalsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAppSelector((s) => s.auth);
  const [level, setLevel] = useState<'L1' | 'L2' | 'L3'>('L1');
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const [actionDialog, setActionDialog] = useState<{
    open: boolean; submissionId: number | null; action: string; kri_id?: number | null;
  }>({ open: false, submissionId: null, action: '' });
  const [comments, setComments] = useState('');
  const [nextApproverId, setNextApproverId] = useState<number | null>(null);

  const [commentDialog, setCommentDialog] = useState<{ open: boolean; statusId: number | null; kriId: number | null }>({
    open: false, statusId: null, kriId: null,
  });
  const [commentText, setCommentText] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['pending-approvals', level],
    queryFn: () => makerCheckerApi.pending({ level }).then((r) => r.data),
  });

  const { data: l2Users = [] } = useQuery({
    queryKey: ['l2-users'],
    queryFn: () => userApi.byRole('L2_APPROVER').then((r) => r.data),
  });

  const { data: l3Users = [] } = useQuery({
    queryKey: ['l3-users'],
    queryFn: () => userApi.byRole('L3_ADMIN').then((r) => r.data),
  });

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

  const items = data?.items || [];
  const nextApprovers = level === 'L1' ? l2Users : level === 'L2' ? l3Users : [];

  const canApprove = hasRole(user?.roles || [], ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']);
  const canEscalate = isL3Admin(user?.roles || []);

  const handleAction = (submissionId: number, action: string) => {
    setActionDialog({ open: true, submissionId, action });
  };

  const confirmAction = () => {
    if (!actionDialog.submissionId) return;
    actionMutation.mutate({
      id: actionDialog.submissionId,
      action: actionDialog.action,
      comments,
      next_approver_id: nextApproverId || undefined,
    });
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>Approvals Queue</Typography>

      <Card>
        <CardContent sx={{ p: 0 }}>
          <Tabs value={level} onChange={(_, v) => setLevel(v)} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
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

          <Box sx={{ p: 2 }}>
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
            ) : items.length === 0 ? (
              <Alert severity="success" sx={{ mt: 1 }}>No pending {level} approvals. All caught up!</Alert>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: 32 }} />
                      <TableCell sx={{ fontWeight: 700 }}>KRI</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>SLA</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Pending With</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Submitted</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Submitted By</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((item: any) => (
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
                          <TableCell>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {item.kri_name || `Status #${item.status_id}`}
                            </Typography>
                            {item.kri_code && (
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                {item.kri_code}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            {slaChip(item.rag_status, item.sla_due_dt)}
                          </TableCell>
                          <TableCell>{statusChip(item.final_status)}</TableCell>
                          <TableCell>
                            <Chip
                              label={item.pending_with || '—'}
                              size="small"
                              variant="outlined"
                              sx={{ fontWeight: 600, fontSize: '0.72rem' }}
                            />
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                            {new Date(item.submitted_dt).toLocaleDateString('en-GB')}
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.82rem' }}>
                            {item.submitted_by_name || `User #${item.submitted_by}`}
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center', flexWrap: 'wrap' }}>
                              {canApprove && (
                                <>
                                  <Button
                                    size="small" variant="contained" color="success" startIcon={<CheckCircle />}
                                    onClick={() => handleAction(item.submission_id, 'APPROVED')}
                                    sx={{ fontSize: '0.72rem' }}
                                  >
                                    Approve
                                  </Button>
                                  <Button
                                    size="small" variant="outlined" color="warning" startIcon={<Replay />}
                                    onClick={() => handleAction(item.submission_id, 'REWORK')}
                                    sx={{ fontSize: '0.72rem' }}
                                  >
                                    Rework
                                  </Button>
                                  <Button
                                    size="small" variant="outlined" color="error" startIcon={<Cancel />}
                                    onClick={() => handleAction(item.submission_id, 'REJECTED')}
                                    sx={{ fontSize: '0.72rem' }}
                                  >
                                    Reject
                                  </Button>
                                </>
                              )}
                              {canEscalate && level !== 'L3' && (
                                <Button
                                  size="small" variant="contained" color="info" startIcon={<ArrowForward />}
                                  onClick={() => handleAction(item.submission_id, 'ESCALATE')}
                                  sx={{ fontSize: '0.72rem' }}
                                >
                                  Escalate
                                </Button>
                              )}
                              <Tooltip title="View Evidence">
                                <IconButton
                                  size="small"
                                  onClick={() => navigate(`/evidence`)}
                                >
                                  <Folder fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Add Comment">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setCommentDialog({ open: true, statusId: item.status_id, kriId: item.kri_id });
                                    setCommentText('');
                                  }}
                                >
                                  <Comment fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          </TableCell>
                        </TableRow>

                        {/* ─── Expandable Audit Trail ─── */}
                        <TableRow>
                          <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
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
          </Box>
        </CardContent>
      </Card>

      {/* ─── Action Confirmation Dialog ───────────────────── */}
      <Dialog
        open={actionDialog.open}
        onClose={() => setActionDialog({ open: false, submissionId: null, action: '' })}
        maxWidth="sm" fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          Confirm: {actionDialog.action} — Submission #{actionDialog.submissionId}
        </DialogTitle>
        <DialogContent dividers>
          <TextField
            label="Comments"
            multiline
            rows={3}
            fullWidth
            value={comments}
            onChange={(e) => setComments(e.target.value)}
            sx={{ mb: 2 }}
            placeholder="Optional: add a note for this action"
          />
          {actionDialog.action === 'APPROVED' && nextApprovers.length > 0 && (
            <FormControl fullWidth>
              <InputLabel>Forward to next approver</InputLabel>
              <Select
                value={nextApproverId || ''}
                label="Forward to next approver"
                onChange={(e) => setNextApproverId(Number(e.target.value))}
              >
                <MenuItem value="">— No further approval needed —</MenuItem>
                {nextApprovers.map((u: any) => (
                  <MenuItem key={u.user_id} value={u.user_id}>{u.full_name} ({u.soe_id})</MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setActionDialog({ open: false, submissionId: null, action: '' })}>Cancel</Button>
          <Button
            variant="contained"
            color={
              actionDialog.action === 'APPROVED' ? 'success'
              : actionDialog.action === 'REJECTED' ? 'error'
              : 'warning'
            }
            onClick={confirmAction}
            disabled={actionMutation.isPending}
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
            label="Comment"
            multiline
            rows={4}
            fullWidth
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
