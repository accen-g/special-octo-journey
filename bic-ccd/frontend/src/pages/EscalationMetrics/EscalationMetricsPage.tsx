import React from 'react';
import {
  Box, Typography, Grid, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  CircularProgress, Alert,
} from '@mui/material';
import { Warning, CheckCircle, Schedule, TrendingUp } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { escalationApi } from '../../api/client';
import api from '../../api/client';
import KpiCard from '../../components/common/KpiCard';

// Canonical table header sx applied to every TableCell in a <TableHead>
const TH_SX = { fontWeight: 700, fontSize: '0.72rem', whiteSpace: 'nowrap' };

export default function EscalationMetricsPage() {
  const { data: rules, isLoading: loadingRules } = useQuery({
    queryKey: ['escalation-rules'],
    queryFn: () => escalationApi.list().then((r) => r.data),
  });

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['escalation-metrics-summary'],
    queryFn: () => api.get('/escalation-metrics/summary').then((r) => r.data),
  });

  const ruleList: any[] = rules || [];
  const escalationEvents: number = summary?.total_escalations ?? 0;
  const pendingEscalations: number = summary?.pending_escalations ?? 0;
  const topRole: string = summary?.top_escalated_role ?? '—';

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>Escalation Metrics</Typography>

      {/* ─── KPI Cards ─────────────────────────────────── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Active Escalation Rules"
            value={ruleList.length}
            subtitle="Configured thresholds"
            borderColor="#2471a3"
            icon={<Schedule />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Total Escalation Events"
            value={escalationEvents}
            subtitle="All time"
            borderColor="#e67e22"
            icon={<Warning />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Pending Escalations"
            value={pendingEscalations}
            subtitle="Awaiting action"
            borderColor="#922b21"
            icon={<TrendingUp />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Most Escalated To"
            value={topRole}
            subtitle="By event count"
            borderColor="#1e8449"
            icon={<CheckCircle />}
          />
        </Grid>
      </Grid>

      {/* ─── Escalation Rules Table ─────────────────────── */}
      <Box sx={{ mb: 2, p: 0, borderRadius: 1, border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Box sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Escalation Rules</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Rules currently governing escalation behaviour
          </Typography>
        </Box>
        {loadingRules ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
        ) : ruleList.length === 0 ? (
          <Alert severity="info" sx={{ m: 2 }}>
            No escalation rules configured. A System Admin can add rules via the Admin panel.
          </Alert>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={TH_SX}>Type</TableCell>
                  <TableCell sx={TH_SX}>Threshold</TableCell>
                  <TableCell sx={TH_SX}>Reminder</TableCell>
                  <TableCell sx={TH_SX}>Max Reminders</TableCell>
                  <TableCell sx={TH_SX}>Escalates To</TableCell>
                  <TableCell sx={TH_SX}>Region</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {ruleList.map((rule: any) => (
                  <TableRow key={rule.config_id} hover>
                    <TableCell>
                      <Chip label={rule.escalation_type} size="small" sx={{ fontWeight: 600 }} />
                    </TableCell>
                    <TableCell>{rule.threshold_hours} hrs</TableCell>
                    <TableCell>{rule.reminder_hours} hrs</TableCell>
                    <TableCell>{rule.max_reminders ?? 3}</TableCell>
                    <TableCell>
                      <Chip label={rule.escalate_to_role} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {rule.region_id ? `Region #${rule.region_id}` : 'Global'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* ─── Activity Breakdown ─────────────────────────── */}
      {summary?.by_type && summary.by_type.length > 0 && (
        <Box sx={{ borderRadius: 1, border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
          <Box sx={{ px: 2, pt: 2, pb: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Events by Escalation Type</Typography>
          </Box>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={TH_SX}>Escalation Type</TableCell>
                  <TableCell sx={{ ...TH_SX, textAlign: 'right' }}>Event Count</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {summary.by_type.map((row: any) => (
                  <TableRow key={row.escalation_type} hover>
                    <TableCell>
                      <Chip label={row.escalation_type} size="small" />
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>{row.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Box>
  );
}
