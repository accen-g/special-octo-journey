import React from 'react';
import {
  Box, Card, CardContent, Typography, Grid, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  CircularProgress, Alert,
} from '@mui/material';
import { Warning, CheckCircle, Schedule, TrendingUp } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { escalationApi } from '../../api/client';
import api from '../../api/client';

// ─── KPI card ────────────────────────────────────────────────
function MetricCard({
  label, value, sub, icon, color,
}: {
  label: string; value: string | number; sub?: string;
  icon: React.ReactNode; color: string;
}) {
  return (
    <Card variant="outlined">
      <CardContent sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
        <Box sx={{
          width: 44, height: 44, borderRadius: 2, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          bgcolor: `${color}18`, color,
        }}>
          {icon}
        </Box>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, lineHeight: 1 }}>{value}</Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, mt: 0.3 }}>{label}</Typography>
          {sub && <Typography variant="caption" sx={{ color: 'text.secondary' }}>{sub}</Typography>}
        </Box>
      </CardContent>
    </Card>
  );
}

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
          <MetricCard
            label="Active Escalation Rules"
            value={ruleList.length}
            sub="Configured thresholds"
            icon={<Schedule />}
            color="#2471a3"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Total Escalation Events"
            value={escalationEvents}
            sub="All time"
            icon={<Warning />}
            color="#e67e22"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Pending Escalations"
            value={pendingEscalations}
            sub="Awaiting action"
            icon={<TrendingUp />}
            color="#922b21"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Most Escalated To"
            value={topRole}
            sub="By event count"
            icon={<CheckCircle />}
            color="#1e8449"
          />
        </Grid>
      </Grid>

      {/* ─── Escalation Rules Table ─────────────────────── */}
      <Card variant="outlined">
        <CardContent sx={{ p: 0 }}>
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
                    <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Threshold</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Reminder</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Max Reminders</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Escalates To</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Region</TableCell>
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
        </CardContent>
      </Card>

      {/* ─── Activity Breakdown ─────────────────────────── */}
      {summary?.by_type && summary.by_type.length > 0 && (
        <Card variant="outlined" sx={{ mt: 2 }}>
          <CardContent sx={{ p: 0 }}>
            <Box sx={{ px: 2, pt: 2, pb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Events by Escalation Type</Typography>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Escalation Type</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="right">Event Count</TableCell>
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
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
