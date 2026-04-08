import { useState, useMemo } from 'react';
import {
  Box, Card, CardContent, Typography, Tabs, Tab, Chip, IconButton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Button, CircularProgress, Tooltip, Dialog, DialogTitle,
  DialogContent, DialogActions, Pagination,
  ToggleButtonGroup, ToggleButton, Select, MenuItem, FormControl, InputLabel,
} from '@mui/material';
import { Comment, Visibility, ViewList, Apps } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { controlApi, lookupApi } from '../../api/client';
import { useAppSelector } from '../../store';
import StatusBadge from '../../components/common/StatusBadge';
import FilterBar from '../../components/common/FilterBar';
import { hasRole } from '../../utils/helpers';
import type { MonthlyStatus, Dimension, Region } from '../../types';

type ViewMode = 'controls' | 'kris';

interface KriMatrixItem {
  kri_id: number;
  kri_code: string;
  kri_name: string;
  region_name: string;
  category_name: string;
  dimensions: Record<string, { status: string; sla_due_dt?: string }>;
}

// ─── Status config for KRI heatmap (Option 2: tinted cell BG) ─
const STATUS_HEAT: Record<string, { cellBg: string; hoverBg: string; color: string; label: string }> = {
  COMPLETED:        { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'Completed'        },
  APPROVED:         { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'Approved'         },
  SLA_MET:          { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'SLA Met'          },
  IN_PROGRESS:      { cellBg: '#eff6ff', hoverBg: '#dbeafe', color: '#1d4ed8', label: 'In Progress'      },
  PENDING_APPROVAL: { cellBg: '#fffbeb', hoverBg: '#fef3c7', color: '#b45309', label: 'Pending Approval' },
  REWORK:           { cellBg: '#fff7ed', hoverBg: '#ffedd5', color: '#c2410c', label: 'Rework'           },
  SLA_BREACHED:     { cellBg: '#fff5f5', hoverBg: '#fee2e2', color: '#dc2626', label: 'SLA Breached'     },
  REJECTED:         { cellBg: '#fdf2f8', hoverBg: '#fce7f3', color: '#9d174d', label: 'Rejected'         },
  NOT_STARTED:      { cellBg: 'transparent', hoverBg: '#f9fafb', color: '#9ca3af', label: 'Not Started'  },
};

// Returns cell bg for TableCell sx
function getStatusCellStyle(status: string) {
  const cfg = STATUS_HEAT[status];
  return cfg ? { bgcolor: cfg.cellBg, hoverBg: cfg.hoverBg } : { bgcolor: 'transparent', hoverBg: '#f9fafb' };
}

// ─── Heatmap cell: colored text only, no icon, no pill ────────
function HeatmapCell({ status, slaDue }: { status: string; slaDue?: string }) {
  const cfg = STATUS_HEAT[status] || { cellBg: 'transparent', hoverBg: '#f9fafb', color: '#9ca3af', label: status };
  return (
    <Tooltip
      title={slaDue ? `${cfg.label} — SLA: ${new Date(slaDue).toLocaleDateString('en-GB')}` : cfg.label}
      arrow
      placement="top"
    >
      <Typography
        aria-label={cfg.label}
        component="span"
        sx={{ fontSize: '0.76rem', fontWeight: 600, color: cfg.color, cursor: 'default', whiteSpace: 'nowrap' }}
      >
        {cfg.label}
      </Typography>
    </Tooltip>
  );
}

// ─── Table column borders ─────────────────────────────────────
const COL_BORDER = { borderRight: '1px solid rgba(0,0,0,0.07)' };
const ROW_BORDER = { borderBottom: '1px solid rgba(0,0,0,0.08)' };

export default function DataControlPage() {
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const { user } = useAppSelector((s) => s.auth);
  const [activeTab, setActiveTab] = useState(0);
  const [page, setPage] = useState(1);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<MonthlyStatus | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('controls');

  // KRI View header filters (client-side)
  const [kriRegionFilter, setKriRegionFilter] = useState('');
  const [kriCategoryFilter, setKriCategoryFilter] = useState('');

  const isManagement = hasRole(user?.roles || [], ['MANAGEMENT']);

  const { data: regions = [] } = useQuery<Region[]>({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: categories = [] } = useQuery<any[]>({
    queryKey: ['categories'],
    queryFn: () => lookupApi.categories().then((r) => r.data),
  });

  const { data: dimensions = [] } = useQuery<Dimension[]>({
    queryKey: ['dimensions'],
    queryFn: () => lookupApi.dimensions().then((r) => r.data),
  });

  const currentDimension = dimensions[activeTab];

  // Control View: paginated query for the selected dimension tab
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
    enabled: !!currentDimension && viewMode === 'controls',
  });

  // KRI View: fetch all controls across all dimensions (no dimension filter)
  const { data: allControlsData, isLoading: allLoading } = useQuery({
    queryKey: ['controls-all', selectedPeriod, selectedRegionId, statusFilter],
    queryFn: () => controlApi.list({
      year: selectedPeriod.year,
      month: selectedPeriod.month,
      region_id: selectedRegionId || undefined,
      status: statusFilter || undefined,
      page: 1,
      page_size: 500,
    }).then((r) => r.data),
    enabled: viewMode === 'kris',
  });

  const items: MonthlyStatus[] = data?.items || [];
  const total = data?.total || 0;

  const { data: auditTrail = [] } = useQuery({
    queryKey: ['audit-trail', selectedStatus?.status_id],
    queryFn: () => controlApi.auditTrail(selectedStatus!.status_id).then((r) => r.data),
    enabled: !!selectedStatus,
  });

  // KRI matrix: aggregate all-dimension data keyed by kri_id
  const kriMatrixRaw = useMemo<KriMatrixItem[]>(() => {
    const allItems: MonthlyStatus[] = allControlsData?.items || [];
    const kriMap = new Map<number, KriMatrixItem>();
    allItems.forEach((item) => {
      if (!kriMap.has(item.kri_id)) {
        kriMap.set(item.kri_id, {
          kri_id: item.kri_id,
          kri_code: item.kri_code || '',
          kri_name: item.kri_name || '',
          region_name: item.region_name || '',
          category_name: (item as any).category_name || '',
          dimensions: {},
        });
      }
      const entry = kriMap.get(item.kri_id)!;
      if (item.dimension_name) {
        entry.dimensions[item.dimension_name] = {
          status: item.status,
          sla_due_dt: item.sla_due_dt,
        };
      }
    });
    return Array.from(kriMap.values());
  }, [allControlsData]);

  // Apply client-side KRI View filters
  const kriMatrix = useMemo(() => {
    return kriMatrixRaw.filter((kri) => {
      if (kriRegionFilter && kri.region_name !== kriRegionFilter) return false;
      if (kriCategoryFilter && kri.category_name !== kriCategoryFilter) return false;
      return true;
    });
  }, [kriMatrixRaw, kriRegionFilter, kriCategoryFilter]);

  const statusCounts = isManagement
    ? {
      pass: items.filter((i: MonthlyStatus) => (i.status as string) === 'PASS').length,
      fail: items.filter((i: MonthlyStatus) => (i.status as string) === 'FAIL').length,
      inProgress: items.filter((i: MonthlyStatus) => (i.status as string) === 'IN_PROGRESS').length,
    }
    : {
      breached: items.filter((i: MonthlyStatus) => i.status === 'SLA_BREACHED').length,
      pending: items.filter((i: MonthlyStatus) => i.status === 'PENDING_APPROVAL').length,
      met: items.filter((i: MonthlyStatus) => (i.status === 'COMPLETED' || i.status === 'APPROVED')).length,
      notStarted: items.filter((i: MonthlyStatus) => i.status === 'NOT_STARTED').length,
    };

  return (
    <Box>
      <FilterBar regions={regions} />

      <Card>
        <CardContent sx={{ p: 0 }}>

          {/* ─── Section header: title + view toggle top-right ─── */}
          <Box sx={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            px: 2, pt: 1.5, pb: viewMode === 'controls' ? 0 : 1.5,
          }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: 0.5, textTransform: 'uppercase', fontSize: '0.72rem' }}>
              Data Control Workbench
            </Typography>

            {/* ─── Sleek segmented toggle — top-right ────────── */}
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(_, v) => v && setViewMode(v)}
              size="small"
              sx={{
                height: 30,
                bgcolor: 'rgba(0,0,0,0.04)',
                borderRadius: 2,
                border: 'none',
                '& .MuiToggleButton-root': {
                  border: 'none',
                  borderRadius: 2,
                  px: 1.5,
                  py: 0.3,
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: 'text.secondary',
                  letterSpacing: 0.2,
                  '&.Mui-selected': {
                    bgcolor: 'white',
                    color: 'primary.main',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.14)',
                    zIndex: 1,
                    '&:hover': { bgcolor: 'white' },
                  },
                  '&:hover': { bgcolor: 'rgba(0,0,0,0.06)' },
                },
              }}
            >
              <ToggleButton value="controls" aria-label="control view">
                <ViewList sx={{ fontSize: 14, mr: 0.5 }} />
                Control View
              </ToggleButton>
              <ToggleButton value="kris" aria-label="kri view">
                <Apps sx={{ fontSize: 14, mr: 0.5 }} />
                KRI View
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>

          {/* ─── 7 Dimension Tabs (Control View only) ─────────── */}
          {viewMode === 'controls' && (
            <Tabs
              value={activeTab}
              onChange={(_, v) => { setActiveTab(v); setPage(1); }}
              variant="scrollable"
              scrollButtons="auto"
              sx={{
                borderBottom: '1px solid',
                borderColor: 'divider',
                '& .MuiTab-root': { py: 1.5, minHeight: 52 },
              }}
            >
              {dimensions.map((dim) => (
                <Tab
                  key={dim.dimension_id}
                  label={
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <Typography variant="body2">{dim.dimension_name}</Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                        Control ID: {dim.dimension_id}
                      </Typography>
                    </Box>
                  }
                />
              ))}
            </Tabs>
          )}

          {/* ─── KRI View header filters ───────────────────────── */}
          {viewMode === 'kris' && (
            <Box sx={{
              display: 'flex', gap: 2, px: 2, pb: 1.5, alignItems: 'center', flexWrap: 'wrap',
              borderBottom: '1px solid', borderColor: 'divider', bgcolor: '#fafafa',
            }}>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Region</InputLabel>
                <Select
                  value={kriRegionFilter}
                  label="Region"
                  onChange={(e) => setKriRegionFilter(e.target.value)}
                >
                  <MenuItem value="">All Regions</MenuItem>
                  {(regions as any[]).map((r: any) => (
                    <MenuItem key={r.region_id} value={r.region_name}>{r.region_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel>Category</InputLabel>
                <Select
                  value={kriCategoryFilter}
                  label="Category"
                  onChange={(e) => setKriCategoryFilter(e.target.value)}
                >
                  <MenuItem value="">All Categories</MenuItem>
                  {(categories as any[]).map((c: any) => (
                    <MenuItem key={c.category_id} value={c.category_name}>{c.category_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {(kriRegionFilter || kriCategoryFilter) && (
                <Button
                  size="small" variant="text" sx={{ fontSize: '0.75rem' }}
                  onClick={() => { setKriRegionFilter(''); setKriCategoryFilter(''); }}
                >
                  Clear
                </Button>
              )}

              <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
                {kriMatrix.length} KRI{kriMatrix.length !== 1 ? 's' : ''}
                {(kriRegionFilter || kriCategoryFilter) ? ' (filtered)' : ''}
              </Typography>
            </Box>
          )}

          {/* ─── Status Filter Chips (Control View) ───────────── */}
          {viewMode === 'controls' && (
            <Box sx={{ display: 'flex', gap: 1, px: 2, py: 1.5, alignItems: 'center', flexWrap: 'wrap', borderBottom: '1px solid', borderColor: 'divider' }}>
              <Chip
                label={`All (${total})`}
                variant={statusFilter === '' ? 'filled' : 'outlined'}
                onClick={() => setStatusFilter('')} size="small" sx={{ fontWeight: 600 }}
              />
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
          )}

          {/* ─── Control View Table ───────────────────────────── */}
          {viewMode === 'controls' && (
            isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
            ) : (
              <TableContainer>
                <Table
                  size="small"
                  sx={{
                    '& th': { ...COL_BORDER, bgcolor: '#fafafa' },
                    '& td': { ...COL_BORDER, ...ROW_BORDER },
                    '& th:last-child, & td:last-child': { borderRight: 'none' },
                  }}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>KRI Code</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>KRI Name</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Region</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Category</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
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
                        <TableCell colSpan={8} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                          No control records found for this period and dimension.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )
          )}

          {viewMode === 'controls' && total > 25 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <Pagination count={Math.ceil(total / 25)} page={page} onChange={(_, p) => setPage(p)} color="primary" />
            </Box>
          )}

          {/* ─── KRI View Heatmap Matrix ───────────────────────── */}
          {viewMode === 'kris' && (
            allLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
            ) : (
              <TableContainer sx={{ overflowX: 'auto' }}>
                <Table
                  size="small"
                  stickyHeader
                  sx={{
                    '& th': { ...COL_BORDER, bgcolor: '#fafafa' },
                    '& td': { ...COL_BORDER, ...ROW_BORDER },
                    '& th:last-child, & td:last-child': { borderRight: 'none' },
                  }}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700, minWidth: 110 }}>KRI Code</TableCell>
                      <TableCell sx={{ fontWeight: 700, minWidth: 190 }}>KRI Name</TableCell>
                      <TableCell sx={{ fontWeight: 700, minWidth: 90 }}>Region</TableCell>
                      <TableCell sx={{ fontWeight: 700, minWidth: 110 }}>Category</TableCell>
                      {dimensions.map((dim) => (
                        <TableCell key={dim.dimension_id} sx={{ fontWeight: 700, minWidth: 130, textAlign: 'center' }}>
                          <Tooltip title={dim.dimension_name} arrow>
                            <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>
                              {dim.dimension_name.length > 16
                                ? dim.dimension_name.slice(0, 15) + '…'
                                : dim.dimension_name}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {kriMatrix.map((kri) => (
                      <TableRow key={kri.kri_id} hover>
                        <TableCell sx={{ fontWeight: 600, fontFamily: 'monospace', fontSize: '0.78rem' }}>{kri.kri_code}</TableCell>
                        <TableCell sx={{ fontSize: '0.82rem' }}>
                          <Typography noWrap sx={{ fontSize: '0.82rem', maxWidth: 190 }}>{kri.kri_name}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={kri.region_name} size="small" sx={{ fontSize: '0.7rem', fontWeight: 600 }} />
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.78rem' }}>
                          <Typography noWrap sx={{ fontSize: '0.78rem', maxWidth: 110 }}>{kri.category_name || '—'}</Typography>
                        </TableCell>
                        {dimensions.map((dim) => {
                          const dimStatus = kri.dimensions[dim.dimension_name];
                          const cellStyle = dimStatus ? getStatusCellStyle(dimStatus.status) : { bgcolor: 'transparent', hoverBg: '#f9fafb' };
                          return (
                            <TableCell
                              key={dim.dimension_id}
                              sx={{
                                ...COL_BORDER,
                                ...ROW_BORDER,
                                py: 0.9,
                                px: 1.2,
                                bgcolor: cellStyle.bgcolor,
                                transition: 'background-color 0.12s',
                                'tr:hover &': { bgcolor: cellStyle.hoverBg },
                              }}
                            >
                              {dimStatus ? (
                                <HeatmapCell status={dimStatus.status} slaDue={dimStatus.sla_due_dt} />
                              ) : (
                                <Typography variant="caption" sx={{ color: '#e2e8f0' }}>—</Typography>
                              )}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    ))}
                    {kriMatrix.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4 + dimensions.length} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                          No KRI records found{kriRegionFilter || kriCategoryFilter ? ' matching the selected filters' : ' for this period'}.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )
          )}
        </CardContent>
      </Card>

      {/* ─── Detail / Audit Trail Dialog ──────────────────────── */}
      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          {selectedStatus?.kri_code} — {selectedStatus?.kri_name}
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
            {selectedStatus?.status && <StatusBadge status={selectedStatus.status} size="medium" />}
            {selectedStatus?.approval_level && (
              <Chip label={`Approval: ${selectedStatus.approval_level}`} variant="outlined" />
            )}
          </Box>

          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, mt: 2 }}>Audit Trail</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table
              size="small"
              sx={{
                '& th': { ...COL_BORDER, bgcolor: '#fafafa' },
                '& td': { ...COL_BORDER, ...ROW_BORDER },
                '& th:last-child, & td:last-child': { borderRight: 'none' },
              }}
            >
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
