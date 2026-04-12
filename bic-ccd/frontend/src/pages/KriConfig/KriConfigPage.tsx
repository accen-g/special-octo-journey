import React, { useState } from 'react';
import {
  Box, Typography, Button, TextField, InputAdornment, Chip, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Select, MenuItem, FormControl, CircularProgress, Alert, Grid,
} from '@mui/material';
import { Search as SearchIcon, Add as AddIcon, Download as DownloadIcon } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { kriOnboardingApi } from '../../api/client';
import type { KriConfigListItem } from '../../types';
import KpiCard from '../../components/common/KpiCard';
import StatusChip from '../../components/common/StatusChip';

// Canonical table header sx
const TH_SX = { fontWeight: 700, fontSize: '0.72rem', whiteSpace: 'nowrap' };

const statusConfig: Record<string, string> = {
  APPROVED:         'APPROVED',
  PENDING_APPROVAL: 'PENDING_APPROVAL',
  REJECTED:         'REJECTED',
  REWORK:           'REWORK',
  DRAFT:            'DRAFT',
  ACTIVE:           'ACTIVE',
};

const statusLabels: Record<string, string> = {
  APPROVED:         'Approved',
  PENDING_APPROVAL: 'Pending Approval',
  REJECTED:         'Rejected',
  REWORK:           'Rework',
  DRAFT:            'Draft',
  ACTIVE:           'Active',
};

export default function KriConfigPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [colFilters, setColFilters] = useState({
    kri_code: '', kri_name: '', region_name: '', data_provider_name: '',
    metric_owner_name: '', remediation_owner_name: '',
  });

  const { data: rows = [], isLoading, error } = useQuery<KriConfigListItem[]>({
    queryKey: ['kri-onboarding-list'],
    queryFn: () => kriOnboardingApi.list().then(r => r.data),
  });

  // Client-side filtering (mirrors prototype behaviour)
  const filtered = rows.filter(r => {
    const q = search.toLowerCase();
    if (q && !r.kri_code?.toLowerCase().includes(q) && !r.kri_name.toLowerCase().includes(q)) return false;
    if (statusFilter && r.approval_status !== statusFilter) return false;
    for (const [k, v] of Object.entries(colFilters)) {
      if (!v) continue;
      const val = (r as any)[k] ?? '';
      if (!String(val).toLowerCase().includes(v.toLowerCase())) return false;
    }
    return true;
  });

  const counts = {
    total: rows.length,
    approved: rows.filter(r => r.approval_status === 'APPROVED').length,
    pending: rows.filter(r => r.approval_status === 'PENDING_APPROVAL').length,
    rejected: rows.filter(r => r.approval_status === 'REJECTED').length,
    active: rows.filter(r => r.approval_status === 'ACTIVE').length,
  };

  return (
    <Box>
      {/* ── Header ─────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>KRI Configuration</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.3 }}>
            Manage all Key Risk Indicators — onboard, view, filter, and track approval status
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate('/kri-config/new')}>
          New KRI
        </Button>
      </Box>

      {/* ── Stat cards ─────────────────────────────────────── */}
      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        {[
          { label: 'Total KRIs',       count: counts.total,    color: '#003366', onClick: () => setStatusFilter('') },
          { label: 'Active (Live)',     count: counts.active,   color: '#1565c0', onClick: () => setStatusFilter('ACTIVE') },
          { label: 'Approved',          count: counts.approved, color: '#2e7d32', onClick: () => setStatusFilter('APPROVED') },
          { label: 'Pending Approval',  count: counts.pending,  color: '#e65100', onClick: () => setStatusFilter('PENDING_APPROVAL') },
          { label: 'Rejected / Rework', count: counts.rejected, color: '#c62828', onClick: () => setStatusFilter('REJECTED') },
        ].map(card => (
          <Grid item xs={6} sm={2.4} key={card.label}>
            <KpiCard
              title={card.label}
              value={card.count}
              borderColor={card.color}
              onClick={card.onClick}
            />
          </Grid>
        ))}
      </Grid>

      {/* ── Toolbar ────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          size="small"
          placeholder="Search KRI code or name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ maxWidth: 280 }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
        />
        <Box sx={{ display: 'flex', gap: 0.7, flexWrap: 'wrap' }}>
          {['', 'APPROVED', 'PENDING_APPROVAL', 'REJECTED', 'DRAFT', 'REWORK', 'ACTIVE'].map(s => (
            <Chip
              key={s}
              label={s ? (statusLabels[s] ?? s) : 'All'}
              variant={statusFilter === s ? 'filled' : 'outlined'}
              size="small"
              onClick={() => setStatusFilter(s)}
              sx={{
                fontWeight: 600, cursor: 'pointer',
                ...(statusFilter === s ? { bgcolor: 'primary.main', color: '#fff' } : {}),
              }}
            />
          ))}
        </Box>
        <Box sx={{ ml: 'auto' }}>
          <Button variant="outlined" size="small" startIcon={<DownloadIcon />}>Export</Button>
        </Box>
      </Box>

      {/* ── Table ──────────────────────────────────────────── */}
      <Paper sx={{ overflow: 'hidden' }}>
        {error && <Alert severity="error" sx={{ m: 2 }}>Failed to load KRI list</Alert>}
        {isLoading && <Box sx={{ p: 3, textAlign: 'center' }}><CircularProgress size={28} /></Box>}
        {!isLoading && (
          <TableContainer sx={{ maxHeight: 'calc(100vh - 360px)', overflow: 'auto' }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  {['KRI Code','KRI Name','Region','Description','Data Provider','Metric Owner','Remediation Owner','Version','Approval Status','Actions'].map(h => (
                    <TableCell key={h} sx={TH_SX}>{h}</TableCell>
                  ))}
                </TableRow>
                {/* Inline column filters */}
                <TableRow>
                  {(['kri_code','kri_name','region_name','','data_provider_name','metric_owner_name','remediation_owner_name'] as const).map((field, i) => (
                    <TableCell key={i} sx={{ bgcolor: '#fafafa', p: 0.5 }}>
                      {field ? (
                        <TextField
                          size="small"
                          placeholder="Filter…"
                          value={colFilters[field as keyof typeof colFilters]}
                          onChange={e => setColFilters(p => ({ ...p, [field]: e.target.value }))}
                          sx={{ '& .MuiInputBase-root': { fontSize: '0.72rem', height: 28 } }}
                          inputProps={{ style: { padding: '3px 7px' } }}
                        />
                      ) : null}
                    </TableCell>
                  ))}
                  <TableCell sx={{ bgcolor: '#fafafa' }} />
                  <TableCell sx={{ bgcolor: '#fafafa', p: 0.5 }}>
                    <FormControl size="small" sx={{ minWidth: 100 }}>
                      <Select
                        value={statusFilter}
                        onChange={e => setStatusFilter(e.target.value)}
                        displayEmpty
                        sx={{ fontSize: '0.72rem', height: 28 }}
                      >
                        <MenuItem value="">All</MenuItem>
                        {Object.entries(statusLabels).map(([k, v]) => (
                          <MenuItem key={k} value={k} sx={{ fontSize: '0.8rem' }}>{v}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </TableCell>
                  <TableCell sx={{ bgcolor: '#fafafa' }} />
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={10} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                      No KRIs found matching your filters.
                    </TableCell>
                  </TableRow>
                )}
                {filtered.map(row => (
                  <TableRow key={row.kri_id} hover>
                    <TableCell>
                      <Typography
                        sx={{ color: 'primary.main', fontWeight: 700, cursor: 'pointer', fontSize: '0.82rem', '&:hover': { textDecoration: 'underline' } }}
                        onClick={() => navigate(`/kri-config/${row.kri_id}`)}
                      >
                        {row.kri_code ?? `KRI-${row.kri_id}`}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.82rem', maxWidth: 180 }}>{row.kri_name}</TableCell>
                    <TableCell sx={{ fontSize: '0.82rem' }}>{row.region_name ?? '—'}</TableCell>
                    <TableCell sx={{ fontSize: '0.82rem', maxWidth: 220 }}>
                      <Box sx={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 220 }} title={row.description}>
                        {row.description ?? '—'}
                      </Box>
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.82rem' }}>{row.data_provider_name ?? '—'}</TableCell>
                    <TableCell sx={{ fontSize: '0.82rem' }}>{row.metric_owner_name ?? '—'}</TableCell>
                    <TableCell sx={{ fontSize: '0.82rem' }}>{row.remediation_owner_name ?? '—'}</TableCell>
                    <TableCell sx={{ fontSize: '0.82rem', textAlign: 'center' }}>{row.version ?? '1.0'}</TableCell>
                    <TableCell>
                      <StatusChip status={row.approval_status} />
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {row.approval_status === 'PENDING_APPROVAL' && (
                        <Button
                          size="small" variant="contained" color="success" sx={{ fontSize: '0.7rem', py: 0.3, mr: 0.5 }}
                          onClick={() => navigate(`/kri-config/${row.kri_id}`, { state: { tab: 'approval' } })}
                        >
                          Review
                        </Button>
                      )}
                      {(row.approval_status === 'DRAFT' || row.approval_status === 'REWORK') && (
                        <Button
                          size="small" variant="contained" color="warning" sx={{ fontSize: '0.7rem', py: 0.3, mr: 0.5 }}
                          onClick={() => navigate('/kri-config/new', { state: { editKriId: row.kri_id, editStatus: row.approval_status } })}
                        >
                          Edit
                        </Button>
                      )}
                      {/* ACTIVE = Data Control KRIs — no bluesheet, view only */}
                      {row.approval_status !== 'ACTIVE' && (
                        <Button
                          size="small" variant="outlined" sx={{ fontSize: '0.7rem', py: 0.3 }}
                          onClick={() => navigate(row.bluesheet_id ? `/kri-config/${row.kri_id}` : '#')}
                          disabled={!row.bluesheet_id}
                        >
                          View
                        </Button>
                      )}
                      {row.approval_status === 'ACTIVE' && (
                        <Button
                          size="small" variant="outlined" color="info" sx={{ fontSize: '0.7rem', py: 0.3 }}
                          disabled
                        >
                          Data Control
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', px: 2, py: 1, borderTop: '1px solid', borderColor: 'divider', gap: 1 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {filtered.length} of {rows.length} KRIs
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
}
