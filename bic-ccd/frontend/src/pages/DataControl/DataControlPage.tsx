import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, Tabs, Tab, Chip, IconButton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, TextField, Select, MenuItem, FormControl, InputLabel,
  Button, CircularProgress, Tooltip, Dialog, DialogTitle,
  DialogContent, DialogActions, Pagination,
} from '@mui/material';
import { Comment, Visibility, Upload, FilterList } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { controlApi, lookupApi } from '../../api/client';
import { useAppSelector } from '../../store';
import StatusBadge from '../../components/common/StatusBadge';
import FilterBar from '../../components/common/FilterBar';
import { hasRole } from '../../utils/helpers';
import type { MonthlyStatus, Dimension, Region } from '../../types';

export default function DataControlPage() {
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const { user } = useAppSelector((s) => s.auth);
  const [activeTab, setActiveTab] = useState(0);
  const [page, setPage] = useState(1);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<MonthlyStatus | null>(null);
  const [statusFilter, setStatusFilter] = useState('');

  const isManagement = hasRole(user?.roles || [], ['MANAGEMENT']);

  const { data: regions = [] } = useQuery<Region[]>({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: dimensions = [] } = useQuery<Dimension[]>({
    queryKey: ['dimensions'],
    queryFn: () => lookupApi.dimensions().then((r) => r.data),
  });

  const currentDimension = dimensions[activeTab];

  const { data, isLoading } = useQuery({
    queryKey: ['controls', selectedPeriod, selectedRegionId, currentDimension?.dimension_id, statusFilter, page],
    queryFn: () => controlApi.list({
      year: selectedPeriod.year,
      month: selectedPeriod.month,
      region_id: selectedRegionId || undefined,
      dimension_id: currentDimension?.dimension_id,
      status: statusFilter || undefined,
      page,
      page_size: 25,
    }).then((r) => r.data),
    enabled: !!currentDimension,
  });

  const items: MonthlyStatus[] = data?.items || [];
  const total = data?.total || 0;

  const { data: auditTrail = [] } = useQuery({
    queryKey: ['audit-trail', selectedStatus?.status_id],
    queryFn: () => controlApi.auditTrail(selectedStatus!.status_id).then((r) => r.data),
    enabled: !!selectedStatus,
  });

  const statusCounts = isManagement
    ? {
        pass: items.filter((i) => i.status === 'PASS').length,
        fail: items.filter((i) => i.status === 'FAIL').length,
        inProgress: items.filter((i) => i.status === 'IN_PROGRESS').length,
      }
    : {
        breached: items.filter((i) => i.status === 'SLA_BREACHED').length,
        pending: items.filter((i) => i.status === 'PENDING_APPROVAL').length,
        met: items.filter((i) => i.status === 'COMPLETED' || i.status === 'APPROVED').length,
        notStarted: items.filter((i) => i.status === 'NOT_STARTED').length,
      };

  return (
    <Box>
      <FilterBar regions={regions} />

      <Card>
        <CardContent sx={{ p: 0 }}>
          {/* ─── 7 Dimension Tabs ─────────────────────────── */}
          <Tabs
            value={activeTab}
            onChange={(_, v) => { setActiveTab(v); setPage(1); }}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              borderBottom: '1px solid',
              borderColor: 'divider',
              '& .MuiTab-root': { py: 1.5, minHeight: 42 },
            }}
          >
            {dimensions.map((dim, i) => (
              <Tab
                key={dim.dimension_id}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {dim.dimension_name}
                  </Box>
                }
              />
            ))}
          </Tabs>

          {/* ─── Quick status filter chips ────────────────── */}
          <Box sx={{ display: 'flex', gap: 1, p: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip label={`All (${total})`} variant={statusFilter === '' ? 'filled' : 'outlined'}
              onClick={() => setStatusFilter('')} size="small" sx={{ fontWeight: 600 }} />
            {isManagement ? (
              <>
                <Chip label={`✓ Pass (${(statusCounts as any).pass})`}
                  variant={statusFilter === 'PASS' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('PASS')} size="small" color="success" sx={{ fontWeight: 600 }} />
                <Chip label={`✕ Fail (${(statusCounts as any).fail})`}
                  variant={statusFilter === 'FAIL' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('FAIL')} size="small" color="error" sx={{ fontWeight: 600 }} />
                <Chip label={`▶ In Progress (${(statusCounts as any).inProgress})`}
                  variant={statusFilter === 'IN_PROGRESS' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('IN_PROGRESS')} size="small" color="info" sx={{ fontWeight: 600 }} />
              </>
            ) : (
              <>
                <Chip label={`✕ Breached (${(statusCounts as any).breached})`}
                  variant={statusFilter === 'SLA_BREACHED' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('SLA_BREACHED')} size="small" color="error" sx={{ fontWeight: 600 }} />
                <Chip label={`⏳ Pending (${(statusCounts as any).pending})`}
                  variant={statusFilter === 'PENDING_APPROVAL' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('PENDING_APPROVAL')} size="small" color="warning" sx={{ fontWeight: 600 }} />
                <Chip label={`✓ SLA Met (${(statusCounts as any).met})`}
                  variant={statusFilter === 'COMPLETED' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('COMPLETED')} size="small" color="success" sx={{ fontWeight: 600 }} />
                <Chip label={`— Not Started (${(statusCounts as any).notStarted})`}
                  variant={statusFilter === 'NOT_STARTED' ? 'filled' : 'outlined'}
                  onClick={() => setStatusFilter('NOT_STARTED')} size="small" sx={{ fontWeight: 600 }} />
              </>
            )}
          </Box>

          {/* ─── Data Table ───────────────────────────────── */}
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>KRI Code</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>KRI Name</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Region</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Category</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>RAG</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>SLA Due</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Approval</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {items.map((row) => (
                    <TableRow
                      key={row.status_id}
                      hover
                      sx={{ '&:hover': { bgcolor: '#f8f9fa' }, cursor: 'pointer' }}
                      onClick={() => { setSelectedStatus(row); setDetailOpen(true); }}
                    >
                      <TableCell sx={{ fontWeight: 600, fontFamily: 'monospace', fontSize: '0.78rem' }}>{row.kri_code}</TableCell>
                      <TableCell sx={{ fontSize: '0.82rem', maxWidth: 250 }}>
                        <Typography noWrap sx={{ fontSize: '0.82rem' }}>{row.kri_name}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={row.region_name} size="small" sx={{ fontSize: '0.7rem', fontWeight: 600 }} />
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.78rem' }}>{row.category_name}</TableCell>
                      <TableCell><StatusBadge status={row.status} /></TableCell>
                      <TableCell>
                        {row.rag_status && <StatusBadge status={row.rag_status} type="rag" />}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.78rem' }}>
                        {row.sla_due_dt ? new Date(row.sla_due_dt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '—'}
                      </TableCell>
                      <TableCell>
                        {row.approval_level ? (
                          <Chip label={row.approval_level} size="small" variant="outlined" sx={{ fontSize: '0.7rem', fontWeight: 700 }} />
                        ) : '—'}
                      </TableCell>
                      <TableCell align="center">
                        <Tooltip title="View details">
                          <IconButton size="small"><Visibility fontSize="small" /></IconButton>
                        </Tooltip>
                        <Tooltip title="Comments">
                          <IconButton size="small"><Comment fontSize="small" /></IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                  {items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={9} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                        No control records found for this period and dimension.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {total > 25 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <Pagination count={Math.ceil(total / 25)} page={page} onChange={(_, p) => setPage(p)} color="primary" />
            </Box>
          )}
        </CardContent>
      </Card>

      {/* ─── Detail / Audit Trail Dialog ──────────────────── */}
      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          {selectedStatus?.kri_code} — {selectedStatus?.kri_name}
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
            {selectedStatus?.status && <StatusBadge status={selectedStatus.status} size="medium" />}
            {selectedStatus?.rag_status && <StatusBadge status={selectedStatus.rag_status} type="rag" size="medium" />}
            {selectedStatus?.approval_level && (
              <Chip label={`Approval: ${selectedStatus.approval_level}`} variant="outlined" />
            )}
          </Box>

          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, mt: 2 }}>Audit Trail</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Action</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>By</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Comments</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status Change</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {auditTrail.map((a: any) => (
                  <TableRow key={a.audit_id}>
                    <TableCell><Chip label={a.action} size="small" sx={{ fontWeight: 600, fontSize: '0.7rem' }} /></TableCell>
                    <TableCell sx={{ fontSize: '0.82rem' }}>{a.performer_name || a.performed_by}</TableCell>
                    <TableCell sx={{ fontSize: '0.78rem' }}>
                      {new Date(a.performed_dt).toLocaleString('en-GB')}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.82rem' }}>{a.comments || '—'}</TableCell>
                    <TableCell sx={{ fontSize: '0.78rem' }}>{a.previous_status} → {a.new_status}</TableCell>
                  </TableRow>
                ))}
                {auditTrail.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                      No audit trail entries yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
