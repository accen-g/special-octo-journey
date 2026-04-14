import React from 'react';
import { Box, Grid, Card, CardContent, Typography, CircularProgress } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, BarChart, Bar, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { dashboardApi, lookupApi } from '../../api/client';
import { useAppSelector } from '../../store';
import KpiCard from '../../components/common/KpiCard';
import FilterBar from '../../components/common/FilterBar';
import { hasRole } from '../../utils/helpers';
import type { DashboardSummary, TrendDataPoint, DimensionBreakdown, Region } from '../../types';

const COLORS = { met: '#27ae60', breached: '#c0392b', notStarted: '#bdc3c7', pending: '#f39c12' };
const MGMT_COLORS = { pass: '#27ae60', fail: '#c0392b', inProgress: '#f39c12' };

export default function DashboardPage() {
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const { user } = useAppSelector((s) => s.auth);
  const navigate = useNavigate();
  const isManagement = hasRole(user?.roles || [], ['MANAGEMENT']);
  const params = { year: selectedPeriod.year, month: selectedPeriod.month, region_id: selectedRegionId || undefined };

  const { data: regions = [] } = useQuery<Region[]>({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: summary, isLoading } = useQuery<DashboardSummary>({
    queryKey: ['dashboard-summary', params],
    queryFn: () => dashboardApi.summary(params).then((r) => r.data),
  });

  const { data: trend = [] } = useQuery<TrendDataPoint[]>({
    queryKey: ['dashboard-trend', selectedRegionId, selectedPeriod],
    queryFn: () => dashboardApi.trend({
      months: 6,
      region_id: selectedRegionId || undefined,
      year: selectedPeriod.year,
      month: selectedPeriod.month,
    }).then((r) => r.data),
  });

  const { data: dimBreakdown = [] } = useQuery<DimensionBreakdown[]>({
    queryKey: ['dashboard-dimension', params],
    queryFn: () => dashboardApi.dimensionBreakdown(params).then((r) => r.data),
  });

  const { data: slaDist } = useQuery({
    queryKey: ['dashboard-sla-dist', params],
    queryFn: () => dashboardApi.slaDistribution(params).then((r) => r.data),
  });

  if (isLoading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}><CircularProgress /></Box>;
  }

  const s = summary || {
    total_kris: 0, sla_met: 0, sla_met_pct: 0, sla_breached: 0, sla_breached_pct: 0,
    not_started: 0, not_started_pct: 0, pending_approvals: 0, pending_by_level: {},
    regions: [], period: '', mom_sla_met_pct: undefined, mom_sla_breached_delta: undefined, mom_period_label: undefined,
  };

  // Region subtitle: show selected region code(s) from backend (already scoped)
  const regionSubtitle = s.regions?.join(' · ') || 'All Regions';

  // Pending approvals breakdown (L1/L2/L3 percentages)
  const pendingTotal = s.pending_approvals || 0;
  const pendingByLevel = s.pending_by_level || {};
  const pendingBreakdown = pendingTotal > 0
    ? Object.entries(pendingByLevel)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([level, count]) => `${level}: ${Math.round((count / pendingTotal) * 100)}%`)
        .join(' | ')
    : null;

  // Month-over-month trend strings (dynamic from backend)
  const momLabel = s.mom_period_label || '';
  const momSlaMetTrend = s.mom_sla_met_pct != null
    ? `${Math.abs(s.mom_sla_met_pct)}% vs ${momLabel}`
    : undefined;
  const momSlaMetDir = s.mom_sla_met_pct != null
    ? (s.mom_sla_met_pct < 0 ? 'down' : 'up') as 'up' | 'down'
    : undefined;
  // Management Pass card: improvement (positive) → green → 'down' in KpiCard convention
  const momPassDir = s.mom_sla_met_pct != null
    ? (s.mom_sla_met_pct >= 0 ? 'down' : 'up') as 'up' | 'down'
    : undefined;
  const momBreachedTrend = s.mom_sla_breached_delta != null
    ? `${s.mom_sla_breached_delta > 0 ? '+' : ''}${s.mom_sla_breached_delta} vs ${momLabel}${Math.abs(s.mom_sla_breached_delta || 0) > 2 ? ' — Critical' : ''}`
    : undefined;
  const momBreachedDir = s.mom_sla_breached_delta != null
    ? (s.mom_sla_breached_delta > 0 ? 'up' : 'down') as 'up' | 'down'
    : undefined;

  // Navigate to /data-control with pre-set filters
  const goToDataControl = (status: string) => {
    const selectedRegion = regions.find((r) => r.region_id === selectedRegionId);
    const qp = new URLSearchParams({
      period_year: String(selectedPeriod.year),
      period_month: String(selectedPeriod.month),
      status,
    });
    if (selectedRegion) qp.set('region_id', String(selectedRegionId));
    navigate(`/data-control?${qp.toString()}`);
  };

  // Management sees PASS/FAIL/IN PROGRESS; others see raw SLA statuses
  const inProgressCount = (slaDist?.not_started || s.not_started) + (s.pending_approvals || 0);
  const donutData = isManagement
    ? [
        { name: 'Pass', value: slaDist?.sla_met || s.sla_met, color: MGMT_COLORS.pass },
        { name: 'Fail', value: slaDist?.sla_breached || s.sla_breached, color: MGMT_COLORS.fail },
        { name: 'In Progress', value: inProgressCount, color: MGMT_COLORS.inProgress },
      ]
    : [
        { name: 'SLA Met', value: slaDist?.sla_met || s.sla_met, color: COLORS.met },
        { name: 'SLA Breach', value: slaDist?.sla_breached || s.sla_breached, color: COLORS.breached },
        { name: 'Not Started', value: slaDist?.not_started || s.not_started, color: COLORS.notStarted },
      ];

  // Management view: map raw SLA statuses → PASS / FAIL / IN PROGRESS
  const dimBreakdownForCharts = dimBreakdown.map((d) =>
    isManagement
      ? { ...d, Pass: d.sla_met, Fail: d.breached, 'In Progress': d.not_started }
      : d
  );

  const radarData = dimBreakdownForCharts.map((d) => ({
    dimension: d.dimension_name.replace('Completeness & Accuracy', 'Completeness & Acc')
      .replace('Adjustments Tracking', 'Adj. Tracking')
      .replace('Change Governance', 'Change Gov.'),
    ...(isManagement
      ? { Pass: d.sla_met, Fail: d.breached, 'In Progress': d.not_started }
      : { Met: d.sla_met, Breached: d.breached, 'Not Started': d.not_started }
    ),
  }));

  return (
    <Box>
      <FilterBar regions={regions} />

      {/* ─── KPI Cards Row ─────────────────────────────── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2.4}>
          <KpiCard
            title="Total KRIs"
            value={s.total_kris}
            subtitle={regionSubtitle}
            detail="— Active Framework"
            borderColor="#003366"
            onClick={() => goToDataControl('ALL')}
          />
        </Grid>
        {isManagement ? (
          <>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="Pass"
                value={s.sla_met}
                subtitle={`${s.sla_met_pct}% of total`}
                trend={momSlaMetTrend}
                trendDirection={momPassDir}
                detail="— Controls completed"
                borderColor="#27ae60"
                onClick={() => goToDataControl('SLA_MET')}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="Fail"
                value={s.sla_breached}
                subtitle={`${s.sla_breached_pct}% — Needs attention`}
                trend={momBreachedTrend}
                trendDirection={momBreachedDir}
                detail="— Controls failed"
                borderColor="#c0392b"
                alert
                onClick={() => goToDataControl('BREACHED')}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="In Progress"
                value={inProgressCount}
                subtitle={`${s.not_started + s.pending_approvals} KRIs active`}
                detail="— Pending or not started"
                borderColor="#f39c12"
                onClick={() => goToDataControl('NOT_STARTED')}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="Pending Approvals"
                value={s.pending_approvals}
                subtitle={pendingBreakdown || 'Awaiting sign-off'}
                detail="— Action required"
                borderColor="#e67e22"
                alert
                onClick={() => goToDataControl('PENDING_APPROVAL')}
              />
            </Grid>
          </>
        ) : (
          <>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="SLA Met"
                value={s.sla_met}
                subtitle={`${s.sla_met_pct}% of total`}
                trend={momSlaMetTrend}
                trendDirection={momSlaMetDir}
                borderColor="#27ae60"
                onClick={() => goToDataControl('SLA_MET')}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="SLA Breached"
                value={s.sla_breached}
                subtitle={`${s.sla_breached_pct}% — Data not received`}
                trend={momBreachedTrend}
                trendDirection={momBreachedDir}
                borderColor="#c0392b"
                onClick={() => goToDataControl('BREACHED')}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="Not Started"
                value={s.not_started}
                subtitle={`${s.not_started_pct}% — SLA window open`}
                detail="— Awaiting data"
                borderColor="#95a5a6"
                onClick={() => goToDataControl('NOT_STARTED')}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <KpiCard
                title="Pending Approvals"
                value={s.pending_approvals}
                subtitle={pendingBreakdown || 'Approvals required'}
                detail="All SLA Breached KRIs"
                borderColor="#c0392b"
                alert
                onClick={() => goToDataControl('PENDING_APPROVAL')}
              />
            </Grid>
          </>
        )}
      </Grid>

      {/* ─── Charts Row 1: Donut + Trend Line ──────────── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={5}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography sx={{ fontSize: '0.7rem' }}>●</Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                  {isManagement ? 'Control Status Distribution' : 'SLA Status Distribution'}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ fontSize: '0.72rem', color: 'text.secondary', mb: 2 }}>
                {s.period} · All KRIs
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ResponsiveContainer width="50%" height={200}>
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      dataKey="value"
                      stroke="none"
                    >
                      {donutData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {donutData.map((d) => (
                    <Box key={d.name} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ width: 12, height: 12, borderRadius: '2px', bgcolor: d.color }} />
                      <Typography variant="body2" sx={{ fontSize: '0.78rem' }}>{d.name}</Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography sx={{ fontSize: '0.7rem' }}>📈</Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                  SLA Compliance Trend — 6 Months
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ fontSize: '0.72rem', color: 'text.secondary', mb: 1 }}>
                KRI count by status per month
              </Typography>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e4e8" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="sla_met" stroke={isManagement ? MGMT_COLORS.pass : COLORS.met} strokeWidth={2} dot={{ r: 4 }} name={isManagement ? 'Pass' : 'SLA Met'} />
                  <Line type="monotone" dataKey="sla_breached" stroke={isManagement ? MGMT_COLORS.fail : COLORS.breached} strokeWidth={2} dot={{ r: 4 }} name={isManagement ? 'Fail' : 'SLA Breached'} />
                  <Line type="monotone" dataKey="not_started" stroke={isManagement ? MGMT_COLORS.inProgress : COLORS.notStarted} strokeWidth={2} dot={{ r: 4 }} name={isManagement ? 'In Progress' : 'Not Started'} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* ─── Charts Row 2: Dimension Breakdown + Radar ──── */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography sx={{ fontSize: '0.7rem' }}>📊</Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                  Control Dimension Breakdown
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ fontSize: '0.72rem', color: 'text.secondary', mb: 1 }}>
                KRI count by control type · {s.period}
              </Typography>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={dimBreakdownForCharts} layout="vertical" margin={{ left: 100 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e4e8" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="dimension_name"
                    tick={{ fontSize: 10 }}
                    width={100}
                    tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 18) + '…' : v}
                  />
                  <Tooltip />
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                  {isManagement ? (
                    <>
                      <Bar dataKey="Pass" fill={MGMT_COLORS.pass} name="Pass" stackId="a" barSize={16} />
                      <Bar dataKey="Fail" fill={MGMT_COLORS.fail} name="Fail" stackId="a" barSize={16} />
                      <Bar dataKey="In Progress" fill={MGMT_COLORS.inProgress} name="In Progress" stackId="a" barSize={16} />
                    </>
                  ) : (
                    <>
                      <Bar dataKey="sla_met" fill={COLORS.met} name="SLA Met" stackId="a" barSize={16} />
                      <Bar dataKey="breached" fill={COLORS.breached} name="Breached" stackId="a" barSize={16} />
                      <Bar dataKey="not_started" fill={COLORS.notStarted} name="Not Started" stackId="a" barSize={16} />
                    </>
                  )}
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography sx={{ fontSize: '0.7rem' }}>🛡</Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                  Control Health Radar
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ fontSize: '0.72rem', color: 'text.secondary', mb: 1 }}>
                {isManagement ? 'Pass vs Fail vs In Progress per dimension' : 'Met vs Breached vs Not Started per dimension'}
              </Typography>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                  <PolarGrid stroke="#e0e4e8" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 9 }} />
                  <PolarRadiusAxis tick={{ fontSize: 9 }} />
                  {isManagement ? (
                    <>
                      <Radar name="Pass" dataKey="Pass" stroke={MGMT_COLORS.pass} fill={MGMT_COLORS.pass} fillOpacity={0.3} />
                      <Radar name="Fail" dataKey="Fail" stroke={MGMT_COLORS.fail} fill={MGMT_COLORS.fail} fillOpacity={0.3} />
                      <Radar name="In Progress" dataKey="In Progress" stroke={MGMT_COLORS.inProgress} fill={MGMT_COLORS.inProgress} fillOpacity={0.2} />
                    </>
                  ) : (
                    <>
                      <Radar name="Met" dataKey="Met" stroke={COLORS.met} fill={COLORS.met} fillOpacity={0.3} />
                      <Radar name="Breached" dataKey="Breached" stroke={COLORS.breached} fill={COLORS.breached} fillOpacity={0.3} />
                      <Radar name="Not Started" dataKey="Not Started" stroke={COLORS.notStarted} fill={COLORS.notStarted} fillOpacity={0.2} />
                    </>
                  )}
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
