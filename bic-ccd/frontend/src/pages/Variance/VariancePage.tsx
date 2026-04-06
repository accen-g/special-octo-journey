import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, Button, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Tabs, Tab,
} from '@mui/material';
import { TrendingUp, CheckCircle, Cancel } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { varianceApi } from '../../api/client';
import { useAppSelector } from '../../store';
import { hasRole } from '../../utils/helpers';

export default function VariancePage() {
  const queryClient = useQueryClient();
  const { user } = useAppSelector((s) => s.auth);
  const [tab, setTab] = useState(0);
  const [reviewDialog, setReviewDialog] = useState<{ open: boolean; id: number | null; action: string }>({
    open: false, id: null, action: '',
  });
  const [reviewComments, setReviewComments] = useState('');

  // Check if user can review/approve variance (L2+, L3_ADMIN, SYSTEM_ADMIN)
  const canReviewVariance = hasRole(user?.roles || [], ['L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN']);

  const { data, isLoading } = useQuery({
    queryKey: ['variance-pending'],
    queryFn: () => varianceApi.pending().then((r) => r.data),
  });

  const reviewMutation = useMutation({
    mutationFn: (params: { id: number; action: string; comments: string }) =>
      varianceApi.review(params.id, { action: params.action, comments: params.comments }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['variance-pending'] });
      setReviewDialog({ open: false, id: null, action: '' });
      setReviewComments('');
    },
  });

  const items = data?.items || [];

  const getVarianceChip = (pct: number) => {
    const abs = Math.abs(pct);
    if (abs <= 10) return <Chip label={`${pct.toFixed(1)}% ✓ PASS`} size="small" sx={{ bgcolor: '#e8f8f0', color: '#1e8449', fontWeight: 700, fontSize: '0.72rem' }} />;
    return <Chip label={`${pct.toFixed(1)}% ✕ FAIL`} size="small" sx={{ bgcolor: '#fdecea', color: '#922b21', fontWeight: 700, fontSize: '0.72rem' }} />;
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>Variance Analysis</Typography>

      <Card>
        <CardContent sx={{ p: 0 }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
            <Tab label="Pending Review" />
            <Tab label="All Submissions" />
          </Tabs>

          <Box sx={{ p: 2 }}>
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
            ) : items.length === 0 ? (
              <Alert severity="success">No pending variance reviews.</Alert>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>ID</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Variance %</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Commentary</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Submitted</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((v: any) => (
                      <TableRow key={v.variance_id} hover>
                        <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>#{v.variance_id}</TableCell>
                        <TableCell>{getVarianceChip(v.variance_pct)}</TableCell>
                        <TableCell sx={{ fontSize: '0.82rem', maxWidth: 300 }}>
                          <Typography noWrap sx={{ fontSize: '0.82rem' }}>{v.commentary}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={v.review_status} size="small" variant="outlined" sx={{ fontWeight: 600, fontSize: '0.72rem' }} />
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.78rem' }}>
                          {new Date(v.submitted_dt).toLocaleString('en-GB')}
                        </TableCell>
                        <TableCell align="center">
                          <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                            {canReviewVariance && (
                              <>
                                <Button
                                  size="small" variant="contained" color="success"
                                  onClick={() => setReviewDialog({ open: true, id: v.variance_id, action: 'APPROVED' })}
                                  sx={{ fontSize: '0.72rem' }}
                                >
                                  Approve
                                </Button>
                                <Button
                                  size="small" variant="outlined" color="error"
                                  onClick={() => setReviewDialog({ open: true, id: v.variance_id, action: 'REJECTED' })}
                                  sx={{ fontSize: '0.72rem' }}
                                >
                                  Reject
                                </Button>
                              </>
                            )}
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        </CardContent>
      </Card>

      <Dialog open={reviewDialog.open} onClose={() => setReviewDialog({ open: false, id: null, action: '' })} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          {reviewDialog.action} Variance #{reviewDialog.id}
        </DialogTitle>
        <DialogContent dividers>
          <TextField label="Review Comments" multiline rows={3} fullWidth value={reviewComments} onChange={(e) => setReviewComments(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReviewDialog({ open: false, id: null, action: '' })}>Cancel</Button>
          <Button
            variant="contained"
            color={reviewDialog.action === 'APPROVED' ? 'success' : 'error'}
            onClick={() => reviewDialog.id && reviewMutation.mutate({ id: reviewDialog.id, action: reviewDialog.action, comments: reviewComments })}
            disabled={reviewMutation.isPending}
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
