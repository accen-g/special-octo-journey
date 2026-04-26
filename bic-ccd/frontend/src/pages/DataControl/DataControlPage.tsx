/**
 * DataControlPage — Data Control Workbench
 *
 * USER JOURNEY (L3 override path):
 *   1. L3/SYSTEM_ADMIN opens /data-control → KRI VIEW (heatmap)
 *   2. Backend list_controls response now includes region_id + dimension_code per row
 *   3. KriMatrixItem.dimensions stores status_id, approval_level, dimension_code,
 *      dimension_id per cell so the renderer has everything it needs
 *   4. HeatmapCell: if user is L3/SYSTEM_ADMIN AND cell.status === 'PENDING_APPROVAL'
 *      AND cell.approval_level === 'L3' AND user's region assignment covers the KRI's
 *      region → renders a clickable MUI Chip with Edit icon (amber, same chip styling)
 *   5. Non-L3 users or non-eligible cells → renders plain text label (unchanged)
 *   6. Chip click → setOverrideTarget → L3OverrideModal opens
 *   7. Modal submit → POST /api/data-control/{statusId}/l3-override
 *      SUCCESS: invalidates ['controls-all'] cache → heatmap refreshes, modal closes
 *      ERROR:   inline Alert in modal, modal stays open
 *   8. Modal cancel → clearOverrideTarget → modal closes, no API call
 *
 * EMPTY / LOADING / ERROR states:
 *   - Grid shows CircularProgress while data loads
 *   - "No KRI records found" row for empty filter results
 *   - L3 override chip only rendered for eligible cells; no UI change for others
 */
import { useState, useMemo, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Tabs, Tab, Chip, IconButton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Button, CircularProgress, Tooltip, Dialog, DialogTitle,
  DialogContent, DialogActions, Pagination,
  ToggleButtonGroup, ToggleButton,
} from '@mui/material';
import { Comment, Visibility, ViewList, Apps, Edit } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { controlApi, lookupApi } from '../../api/client';
import { useAppSelector, useAppDispatch, setPeriod, setRegion } from '../../store';
import StatusBadge from '../../components/common/StatusBadge';
import FilterBar from '../../components/common/FilterBar';
import GlobalFilterToolbar from '../../components/common/GlobalFilterToolbar';
import TableHeaderFilters from '../../components/common/TableHeaderFilters';
import L3OverrideModal from '../../components/grid/L3OverrideModal';
import { hasRole } from '../../utils/helpers';
import type { MonthlyStatus, Dimension, Region } from '../../types';

// Map dashboard card status keys to control filter values
const DASHBOARD_STATUS_MAP: Record<string, string> = {
  SLA_MET: 'COMPLETED',
  BREACHED: 'SLA_BREACHED',
  NOT_STARTED: 'NOT_STARTED',
  PENDING_APPROVAL: 'PENDING_APPROVAL',
  ALL: '',
};

type ViewMode = 'controls' | 'kris';

/** State carried per-dimension cell in the KRI view matrix. */
interface DimensionCellData {
  status: string;
  sla_due_dt?: string;
  /** MonthlyControlStatus.status_id — used for audit trail lookups. */
  status_id: number;
  /** Approval level on the record (e.g. 'L3' means it is at L3-pending stage). */
  approval_level?: string;
  /** dimension_code from the backend response. */
  dimension_code?: string;
  /** dimension_id for this control. */
  dimension_id: number;
  /** Active MakerCheckerSubmission.submission_id — present only when approval_level === 'L3'. */
  submission_id?: number;
}

interface KriMatrixItem {
  kri_id: number;
  kri_code: string;
  kri_name: string;
  region_name: string;
  region_id: number;
  category_name: string;
  dimensions: Record<string, DimensionCellData>;
}

/** Context passed to the L3OverrideModal when a chip is clicked. */
interface OverrideTarget {
  submissionId: number;
  kriCode: string;
  kriName: string;
}

// ─── Status config for KRI heatmap ────────────────────────────
const STATUS_HEAT: Record<string, { cellBg: string; hoverBg: string; color: string; label: string }> = {
  COMPLETED:        { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'Completed'        },
  APPROVED:         { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'Approved'         },
  SLA_MET:          { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'SLA Met'          },
  IN_PROGRESS:      { cellBg: 'transparent', hoverBg: '#f9fafb', color: '#1d4ed8', label: 'In Progress'  },
  PENDING_APPROVAL: { cellBg: '#fffbeb', hoverBg: '#fef3c7', color: '#b45309', label: 'Pending Approval' },
  REWORK:           { cellBg: '#fff7ed', hoverBg: '#ffedd5', color: '#c2410c', label: 'Rework'           },
  SLA_BREACHED:     { cellBg: '#fff5f5', hoverBg: '#fee2e2', color: '#dc2626', label: 'SLA Breached'     },
  REJECTED:         { cellBg: '#fdf2f8', hoverBg: '#fce7f3', color: '#9d174d', label: 'Rejected'         },
  NOT_STARTED:      { cellBg: 'transparent', hoverBg: '#f9fafb', color: '#9ca3af', label: 'Not Started'  },
  PASS:             { cellBg: '#f0fdf4', hoverBg: '#dcfce7', color: '#15803d', label: 'Pass'             },
  FAIL:             { cellBg: '#fff5f5', hoverBg: '#fee2e2', color: '#dc2626', label: 'Fail'             },
};

function getStatusCellStyle(status: string) {
  const cfg = STATUS_HEAT[status];
  return cfg ? { bgcolor: cfg.cellBg, hoverBg: cfg.hoverBg } : { bgcolor: 'transparent', hoverBg: '#f9fafb' };
}

// ─── Table column borders ─────────────────────────────────────
const COL_BORDER = { borderRight: '1px solid rgba(0,0,0,0.07)' };
const ROW_BORDER = { borderBottom: '1px solid rgba(0,0,0,0.08)' };

// ─── L3 eligibility check ─────────────────────────────────────
/**
 * Returns true when ALL of the following hold:
 *   - Authenticated user has L3_ADMIN or SYSTEM_ADMIN role
 *   - Cell status is PENDING_APPROVAL
 *   - Cell approval_level is 'L3'
 *   - User holds that role for the KRI's region (or with a null/global region)
 *
 * RBAC is enforced server-side; this check is display-only convenience.
 */
function isL3Eligible(
  cell: DimensionCellData,
  kriRegionId: number,
  userRoles: { role_code: string; region_id: number | null }[],
): boolean {
  if (cell.status !== 'PENDING_APPROVAL') return false;
  if (cell.approval_level !== 'L3') return false;
  // Must have a resolved submission_id to call the maker-checker action endpoint
  if (!cell.submission_id) return false;
  const l3RoleCodes = new Set(['L3_ADMIN', 'SYSTEM_ADMIN', 'ANC_APPROVER_L3']);
  return userRoles.some(
    (r) =>
      l3RoleCodes.has(r.role_code) &&
      (r.region_id === null || r.region_id === kriRegionId),
  );
}

// ─── Heatmap cell renderer ─────────────────────────────────────
interface HeatmapCellProps {
  cell: DimensionCellData;
  kriRegionId: number;
  userRoles: { role_code: string; region_id: number | null }[];
  onOverrideClick: () => void;
}

function HeatmapCell({ cell, kriRegionId, userRoles, onOverrideClick }: HeatmapCellProps) {
  const cfg = STATUS_HEAT[cell.status] || { cellBg: 'transparent', hoverBg: '#f9fafb', color: '#9ca3af', label: cell.status };
  const eligible = isL3Eligible(cell, kriRegionId, userRoles);

  const tooltipTitle = cell.sla_due_dt
    ? `${cfg.label} — SLA: ${new Date(cell.sla_due_dt).toLocaleDateString('en-GB')}`
    : cfg.label;

  if (eligible) {
    // Render a clickable chip with an Edit icon for L3-eligible cells
    return (
      <Tooltip title={`${tooltipTitle} — Click to override`} arrow placement="top">
        <Chip
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, lineHeight: 1 }}>
                {cfg.label}
              </Typography>
              <Edit sx={{ fontSize: 11, opacity: 0.8 }} />
            </Box>
          }
          size="small"
          onClick={(e) => { e.stopPropagation(); onOverrideClick(); }}
          sx={{
            bgcolor: cfg.cellBg || '#fffbeb',
            color: cfg.color,
            border: `1px solid ${cfg.color}30`,
            cursor: 'pointer',
            height: 22,
            fontWeight: 700,
            px: 0.5,
            '& .MuiChip-label': { px: 0.5 },
            '&:hover': { bgcolor: cfg.hoverBg, borderColor: cfg.color },
          }}
        />
      </Tooltip>
    );
  }

  // Non-eligible: plain text label — identical to the original HeatmapCell output
  return (
    <Tooltip title={tooltipTitle} arrow placement="top">
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

// ─── Page ──────────────────────────────────────────────────────
export default function DataControlPage() {
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const { user } = useAppSelector((s) => s.auth);
  const dispatch = useAppDispatch();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(0);
  const [page, setPage] = useState(1);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<MonthlyStatus | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('controls');

  // ── L3 override target ─────────────────────────────────────
  const [overrideTarget, setOverrideTarget] = useState<OverrideTarget | null>(null);

  // Apply query params from dashboard card navigation (runs once on mount)
  useEffect(() => {
    const qpStatus = searchParams.get('status');
    const qpYear = searchParams.get('period_year');
    const qpMonth = searchParams.get('period_month');
    const qpRegionId = searchParams.get('region_id');

    if (qpStatus) {
      const mapped = DASHBOARD_STATUS_MAP[qpStatus] ?? '';
      setStatusFilter(mapped);
    }
    if (qpYear && qpMonth) {
      dispatch(setPeriod({ year: Number(qpYear), month: Number(qpMonth) }));
    }
    if (qpRegionId) {
      dispatch(setRegion(Number(qpRegionId)));
    }
    if (qpStatus || qpYear || qpMonth || qpRegionId) {
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Control View inline column filters
  const [controlFilters, setControlFilters] = useState({
    kriCode: '',
    kriName: '',
    region: '',
    category: '',
    status: '',
    owner: '',
    controlType: '',
  });

  // KRI View inline column filters
  const [kriFilters, setKriFilters] = useState({
    kriCode: '',
    kriName: '',
    region: '',
    category: '',
  });

  // KRI View dimension column filters (keyed by dimension_name)
  const [dimensionFilters, setDimensionFilters] = useState<Record<string, string>>({});

  const isManagement = hasRole(user?.roles || [], ['MANAGEMENT']);
  const userRoles = (user?.roles || []) as { role_code: string; region_id: number | null }[];

  const { data: regions = [] } = useQuery<Region[]>({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: categories = [] } = useQuery<{ category_id: number; category_name: string }[]>({
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
          region_id: item.region_id ?? 0,
          category_name: (item as { category_name?: string }).category_name || '',
          dimensions: {},
        });
      }
      const entry = kriMap.get(item.kri_id)!;
      if (item.dimension_name) {
        entry.dimensions[item.dimension_name] = {
          status: item.status,
          sla_due_dt: item.sla_due_dt,
          status_id: item.status_id,
          approval_level: item.approval_level,
          dimension_code: item.dimension_code,
          dimension_id: item.dimension_id,
          submission_id: (item as { submission_id?: number }).submission_id,
        };
      }
    });
    return Array.from(kriMap.values());
  }, [allControlsData]);

  // Apply client-side Control View filters
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (controlFilters.kriCode && !item.kri_code?.toLowerCase().includes(controlFilters.kriCode.toLowerCase())) return false;
      if (controlFilters.kriName && !item.kri_name?.toLowerCase().includes(controlFilters.kriName.toLowerCase())) return false;
      if (controlFilters.region && item.region_name !== controlFilters.region) return false;
      if (controlFilters.category && item.category_name !== controlFilters.category) return false;
      if (controlFilters.status && item.status !== controlFilters.status) return false;
      return true;
    });
  }, [items, controlFilters]);

  // Apply client-side KRI View filters
  const kriMatrix = useMemo(() => {
    return kriMatrixRaw.filter((kri) => {
      if (kriFilters.kriCode && !kri.kri_code?.toLowerCase().includes(kriFilters.kriCode.toLowerCase())) return false;
      if (kriFilters.kriName && !kri.kri_name?.toLowerCase().includes(kriFilters.kriName.toLowerCase())) return false;
      if (kriFilters.region && kri.region_name !== kriFilters.region) return false;
      if (kriFilters.category && kri.category_name !== kriFilters.category) return false;
      for (const [dimName, filterStatus] of Object.entries(dimensionFilters)) {
        if (filterStatus && kri.dimensions[dimName]?.status !== filterStatus) return false;
      }
      return true;
    });
  }, [kriMatrixRaw, kriFilters, dimensionFilters]);

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
            px: 2, pt: 1.5, pb: 0,
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

          {/* ─── Global Filter Toolbar (Period & Region) ────────── */}
          <GlobalFilterToolbar regions={regions} />

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
                  <Chip label={`✓ Pass (${(statusCounts as { pass: number }).pass})`}
                    variant={statusFilter === 'PASS' ? 'filled' : 'outlined'}
                    onClick={() => setStatusFilter('PASS')} size="small" color="success" sx={{ fontWeight: 600 }} />
                  <Chip label={`✕ Fail (${(statusCounts as { fail: number }).fail})`}
                    variant={statusFilter === 'FAIL' ? 'filled' : 'outlined'}
                    onClick={() => setStatusFilter('FAIL')} size="small" color="error" sx={{ fontWeight: 600 }} />
                  <Chip label={`▶ In Progress (${(statusCounts as { inProgress: number }).inProgress})`}
                    variant={statusFilter === 'IN_PROGRESS' ? 'filled' : 'outlined'}
                    onClick={() => setStatusFilter('IN_PROGRESS')} size="small" color="info" sx={{ fontWeight: 600 }} />
                </>
              ) : (
                <>
                  <Chip label={`✕ Breached (${(statusCounts as { breached: number }).breached})`}
                    variant={statusFilter === 'SLA_BREACHED' ? 'filled' : 'outlined'}
                    onClick={() => setStatusFilter('SLA_BREACHED')} size="small" color="error" sx={{ fontWeight: 600 }} />
                  <Chip label={`⏳ Pending (${(statusCounts as { pending: number }).pending})`}
                    variant={statusFilter === 'PENDING_APPROVAL' ? 'filled' : 'outlined'}
                    onClick={() => setStatusFilter('PENDING_APPROVAL')} size="small" color="warning" sx={{ fontWeight: 600 }} />
                  <Chip label={`✓ SLA Met (${(statusCounts as { met: number }).met})`}
                    variant={statusFilter === 'COMPLETED' ? 'filled' : 'outlined'}
                    onClick={() => setStatusFilter('COMPLETED')} size="small" color="success" sx={{ fontWeight: 600 }} />
                  <Chip label={`— Not Started (${(statusCounts as { notStarted: number }).notStarted})`}
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
                    '& th': { ...COL_BORDER },
                    '& td': { ...COL_BORDER, ...ROW_BORDER },
                    '& th:last-child, & td:last-child': { borderRight: 'none' },
                  }}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>KRI Code</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>KRI Name</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Region</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Category</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Status</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>SLA Due</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Approval</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }} align="center">Actions</TableCell>
                    </TableRow>
                    <TableHeaderFilters
                      filters={[
                        {
                          key: 'kriCode',
                          label: 'KRI Code',
                          type: 'text',
                          value: controlFilters.kriCode,
                          onChange: (v) => setControlFilters({ ...controlFilters, kriCode: v }),
                        },
                        {
                          key: 'kriName',
                          label: 'KRI Name',
                          type: 'text',
                          value: controlFilters.kriName,
                          onChange: (v) => setControlFilters({ ...controlFilters, kriName: v }),
                        },
                        {
                          key: 'region',
                          label: 'Region',
                          type: 'select',
                          value: controlFilters.region,
                          options: regions.map((r) => ({ value: r.region_name, label: r.region_name })),
                          onChange: (v) => setControlFilters({ ...controlFilters, region: v }),
                        },
                        {
                          key: 'category',
                          label: 'Category',
                          type: 'select',
                          value: controlFilters.category,
                          options: categories.map((c) => ({ value: c.category_name, label: c.category_name })),
                          onChange: (v) => setControlFilters({ ...controlFilters, category: v }),
                        },
                        {
                          key: 'status',
                          label: 'Status',
                          type: 'select',
                          value: controlFilters.status,
                          options: [
                            { value: 'PASS', label: 'Pass' },
                            { value: 'FAIL', label: 'Fail' },
                            { value: 'IN_PROGRESS', label: 'In Progress' },
                          ],
                          onChange: (v) => setControlFilters({ ...controlFilters, status: v }),
                        },
                        {
                          key: 'slaDue',
                          label: 'SLA Due',
                          type: 'text',
                          value: '',
                          onChange: () => {},
                        },
                        {
                          key: 'approval',
                          label: 'Approval',
                          type: 'text',
                          value: '',
                          onChange: () => {},
                        },
                        {
                          key: 'actions',
                          label: 'Actions',
                          type: 'text',
                          value: '',
                          onChange: () => {},
                        },
                      ]}
                      borderStyle={{ borderRight: '1px solid rgba(0,0,0,0.07)' }}
                    />
                  </TableHead>
                  <TableBody>
                    {filteredItems.map((row) => (
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
                    {filteredItems.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                          No control records found matching the selected filters.
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
                    '& th': { ...COL_BORDER },
                    '& td': { ...COL_BORDER, ...ROW_BORDER },
                    '& th:last-child, & td:last-child': { borderRight: 'none' },
                  }}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap', minWidth: 110 }}>KRI Code</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap', minWidth: 190 }}>KRI Name</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap', minWidth: 90 }}>Region</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap', minWidth: 110 }}>Category</TableCell>
                      {dimensions.map((dim) => (
                        <TableCell key={dim.dimension_id} sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap', minWidth: 130, textAlign: 'center' }}>
                          <Tooltip title={dim.dimension_name} arrow>
                            <Typography variant="caption" sx={{ fontWeight: 700, display: 'block', color: 'inherit' }}>
                              {dim.dimension_name.length > 16
                                ? dim.dimension_name.slice(0, 15) + '…'
                                : dim.dimension_name}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableHeaderFilters
                      filters={[
                        {
                          key: 'kriCode',
                          label: 'KRI Code',
                          type: 'text',
                          value: kriFilters.kriCode,
                          onChange: (v) => setKriFilters({ ...kriFilters, kriCode: v }),
                        },
                        {
                          key: 'kriName',
                          label: 'KRI Name',
                          type: 'text',
                          value: kriFilters.kriName,
                          onChange: (v) => setKriFilters({ ...kriFilters, kriName: v }),
                        },
                        {
                          key: 'region',
                          label: 'Region',
                          type: 'select',
                          value: kriFilters.region,
                          options: regions.map((r) => ({ value: r.region_name, label: r.region_name })),
                          onChange: (v) => setKriFilters({ ...kriFilters, region: v }),
                        },
                        {
                          key: 'category',
                          label: 'Category',
                          type: 'select',
                          value: kriFilters.category,
                          options: categories.map((c) => ({ value: c.category_name, label: c.category_name })),
                          onChange: (v) => setKriFilters({ ...kriFilters, category: v }),
                        },
                        ...dimensions.map((dim) => ({
                          key: `dim-${dim.dimension_id}`,
                          label: dim.dimension_name,
                          type: 'select' as const,
                          value: dimensionFilters[dim.dimension_name] || '',
                          options: Object.entries(STATUS_HEAT).map(([k, v]) => ({ value: k, label: v.label })),
                          onChange: (v: string) => setDimensionFilters((prev) => ({ ...prev, [dim.dimension_name]: v })),
                        })),
                      ]}
                      borderStyle={{ borderRight: '1px solid rgba(0,0,0,0.07)' }}
                    />
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
                                <HeatmapCell
                                  cell={dimStatus}
                                  kriRegionId={kri.region_id}
                                  userRoles={userRoles}
                                  onOverrideClick={() =>
                                    setOverrideTarget({
                                      submissionId: dimStatus.submission_id!,
                                      kriCode:      kri.kri_code,
                                      kriName:      kri.kri_name,
                                    })
                                  }
                                />
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
                          No KRI records found matching the selected filters.
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
                '& th': { ...COL_BORDER },
                '& td': { ...COL_BORDER, ...ROW_BORDER },
                '& th:last-child, & td:last-child': { borderRight: 'none' },
              }}
            >
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Action</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>By</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Date</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Comments</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>Status Change</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {auditTrail.map((a: { audit_id: number; action: string; performer_name?: string; performed_by: number; performed_dt: string; comments?: string; previous_status?: string; new_status?: string }) => (
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

      {/* ─── L3 Override Modal ─────────────────────────────────── */}
      {overrideTarget && (
        <L3OverrideModal
          open={overrideTarget !== null}
          onClose={() => setOverrideTarget(null)}
          submissionId={overrideTarget.submissionId}
          kriCode={overrideTarget.kriCode}
          kriName={overrideTarget.kriName}
        />
      )}
    </Box>
  );
}
