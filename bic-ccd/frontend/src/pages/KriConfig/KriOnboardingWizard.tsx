import React, { useState, useRef } from 'react';
import {
  Box, Typography, Button, TextField, FormControl, Select,
  MenuItem, FormControlLabel, Checkbox, Alert, CircularProgress, Paper,
  Stepper, Step, StepLabel, Grid, Divider, Autocomplete,
} from '@mui/material';
import { CloudUpload as UploadIcon, CheckCircle as CheckIcon } from '@mui/icons-material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import { kriOnboardingApi, lookupApi, userApi } from '../../api/client';
import type { Region, Category, Dimension, KriBluesheetCreate } from '../../types';

const STEPS = [
  'Basic Info', 'Classification', 'Roles & Responsibilities',
  'Scorecard Coverage', 'Rationale & Scope', 'Runbook Upload', 'Review & Submit',
];

const SCORECARD_OPTIONS = [
  { key: 'sc_uk',           label: 'UK Scorecard' },
  { key: 'sc_finance',      label: 'Finance Scorecard' },
  { key: 'sc_risk',         label: 'Risk Scorecard' },
  { key: 'sc_liquidity',    label: 'Liquidity Report Scorecards' },
  { key: 'sc_capital',      label: 'Capital Report Scorecards' },
  { key: 'sc_risk_reports', label: 'Risk Reports Scorecard' },
  { key: 'sc_markets',      label: 'Markets Products Scorecard' },
] as const;

const emptyForm: KriBluesheetCreate = {
  kri_code: '', kri_name: '', description: '', legacy_kri_id: '',
  region_id: 0, category_id: 0, risk_level: 'MEDIUM',
  threshold: '', circuit_breaker: '', frequency: 'Monthly',
  dq_objectives: '', control_ids: '',
  primary_senior_manager: '', metric_owner_name: '', remediation_owner_name: '',
  bi_metrics_lead: '', data_provider_name: '',
  sc_uk: false, sc_finance: false, sc_risk: false, sc_liquidity: false,
  sc_capital: false, sc_risk_reports: false, sc_markets: false,
  why_selected: '', threshold_rationale: '', limitations: '', kri_calculation: '',
  runbook_version: 'v1.0', runbook_review_date: '', runbook_notes: '',
};

/** Strip empty-string fields that the backend treats as typed (date, int). */
function sanitizePayload(f: KriBluesheetCreate): Record<string, unknown> {
  return {
    ...f,
    runbook_review_date: f.runbook_review_date || null,
    region_id: Number(f.region_id) || 0,
    category_id: Number(f.category_id) || 0,
  };
}

export default function KriOnboardingWizard() {
  const navigate = useNavigate();
  const location = useLocation();
  // When navigated from KriConfigPage with { editKriId, editStatus } we pre-load the existing record
  const editKriId: number | undefined = (location.state as any)?.editKriId;
  const editStatus: string | undefined = (location.state as any)?.editStatus;

  const [step, setStep] = useState(0);
  const [form, setForm] = useState<KriBluesheetCreate>(emptyForm);
  const [runbookFile, setRunbookFile] = useState<File | null>(null);
  const [runbookError, setRunbookError] = useState(false);
  // Pre-seed draftKriId with the editKriId so draft save updates the existing record
  const [draftKriId, setDraftKriId] = useState<number | null>(editKriId ?? null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load existing bluesheet when editing a DRAFT or REWORK record
  const editQuery = useQuery({
    queryKey: ['kri-onboarding-edit-raw', editKriId],
    queryFn: () => kriOnboardingApi.get(editKriId!).then(r => r.data),
    enabled: !!editKriId,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  // Populate form from fetched data (runs once on mount when editing)
  React.useEffect(() => {
    if (!editQuery.data) return;
    const d = editQuery.data as any;
    setForm({
      kri_code: d.kri_code ?? '',
      kri_name: d.kri_name ?? '',
      description: d.description ?? '',
      legacy_kri_id: d.legacy_kri_id ?? '',
      region_id: d.region_id ?? 0,
      category_id: d.category_id ?? 0,
      risk_level: d.risk_level ?? 'MEDIUM',
      threshold: d.threshold ?? '',
      circuit_breaker: d.circuit_breaker ?? '',
      frequency: d.frequency ?? 'Monthly',
      dq_objectives: d.dq_objectives ?? '',
      control_ids: d.control_ids ?? '',
      primary_senior_manager: d.primary_senior_manager ?? '',
      metric_owner_name: d.metric_owner_name ?? '',
      remediation_owner_name: d.remediation_owner_name ?? '',
      bi_metrics_lead: d.bi_metrics_lead ?? '',
      data_provider_name: d.data_provider_name ?? '',
      sc_uk: d.sc_uk ?? false,
      sc_finance: d.sc_finance ?? false,
      sc_risk: d.sc_risk ?? false,
      sc_liquidity: d.sc_liquidity ?? false,
      sc_capital: d.sc_capital ?? false,
      sc_risk_reports: d.sc_risk_reports ?? false,
      sc_markets: d.sc_markets ?? false,
      why_selected: d.why_selected ?? '',
      threshold_rationale: d.threshold_rationale ?? '',
      limitations: d.limitations ?? '',
      kri_calculation: d.kri_calculation ?? '',
      runbook_version: d.runbook_version ?? 'v1.0',
      runbook_review_date: d.runbook_review_date ?? '',
      runbook_notes: d.runbook_notes ?? '',
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editQuery.data]);

  // ── Lookups ────────────────────────────────────────────────
  const { data: regions = [] } = useQuery<Region[]>({
    queryKey: ['regions'], queryFn: () => lookupApi.regions().then(r => r.data),
  });
  const { data: categories = [] } = useQuery<Category[]>({
    queryKey: ['categories'], queryFn: () => lookupApi.categories().then(r => r.data),
  });
  // Dimensions = Control ID options
  const { data: dimensions = [] } = useQuery<Dimension[]>({
    queryKey: ['dimensions'], queryFn: () => lookupApi.dimensions().then(r => r.data),
  });
  // All enrolled app users for role assignment
  const { data: allUsersRaw = [] } = useQuery<any[]>({
    queryKey: ['all-users-list'],
    queryFn: () => userApi.list({ page_size: 500 }).then(r => r.data?.items ?? r.data ?? []),
  });
  const allUsers: { label: string; value: string }[] = (allUsersRaw as any[]).map((u: any) => ({
    label: u.full_name || u.soe_id,
    value: u.full_name || u.soe_id,
  }));

  const isEditing = !!editKriId;

  // ── Mutations ──────────────────────────────────────────────
  const submitMutation = useMutation({
    mutationFn: async (data: KriBluesheetCreate) => {
      if (isEditing && editKriId) {
        // Editing DRAFT or REWORK: save fields first, then resubmit for approval
        await kriOnboardingApi.updateDraft(editKriId, sanitizePayload(data));
        return kriOnboardingApi.resubmit(editKriId);
      }
      return kriOnboardingApi.submit(sanitizePayload(data));
    },
    onSuccess: async (res) => {
      const kriId = isEditing ? editKriId! : res.data.kri_id;
      if (runbookFile) {
        try { await kriOnboardingApi.uploadRunbook(kriId, runbookFile); }
        catch { /* non-fatal — runbook can be re-uploaded from detail page */ }
      }
      navigate(`/kri-config/${kriId}`, { state: { justSubmitted: true } });
    },
  });

  const draftMutation = useMutation({
    mutationFn: (data: KriBluesheetCreate) =>
      draftKriId
        ? kriOnboardingApi.updateDraft(draftKriId, sanitizePayload(data))
        : kriOnboardingApi.saveDraft(sanitizePayload(data)),
    onSuccess: (res) => {
      if (!draftKriId) setDraftKriId(res.data.kri_id);
      navigate('/kri-config');
    },
  });

  // ── Helpers ────────────────────────────────────────────────
  const set = (field: keyof KriBluesheetCreate, value: any) =>
    setForm(p => ({ ...p, [field]: value }));

  // Control IDs: stored as comma-separated string, edited as Set
  const selectedControlIds = new Set(
    (form.control_ids || '').split(',').map(s => s.trim()).filter(Boolean)
  );
  const toggleControlId = (code: string) => {
    const next = new Set(selectedControlIds);
    next.has(code) ? next.delete(code) : next.add(code);
    set('control_ids', Array.from(next).join(','));
  };

  const handleNext = () => {
    // When editing an existing record the runbook already exists on the server — don't force re-upload
    if (step === 5 && !runbookFile && !isEditing) { setRunbookError(true); return; }
    if (step === STEPS.length - 1) { submitMutation.mutate(form); return; }
    setStep(s => s + 1);
  };

  const handleFileSelect = (file: File | null) => {
    if (!file) return;
    const allowed = ['.pdf', '.docx', '.xlsx'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowed.includes(ext)) { alert('Only PDF, DOCX, XLSX files are allowed.'); return; }
    if (file.size > 25 * 1024 * 1024) { alert('Max file size is 25 MB.'); return; }
    setRunbookFile(file);
    setRunbookError(false);
  };

  // Simple labelled text field
  const fl = (label: string, field: keyof KriBluesheetCreate, required = false, multiline = false) => (
    <Box>
      <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>
        {label}{required && <span style={{ color: '#c62828' }}> *</span>}
      </Typography>
      <TextField
        fullWidth size="small" multiline={multiline} rows={multiline ? 3 : undefined}
        value={form[field] as string ?? ''}
        onChange={e => set(field, e.target.value)}
        required={required}
      />
    </Box>
  );

  // Role row — searchable dropdown of enrolled users (freeSolo allows free text fallback)
  const roleRow = (label: string, field: keyof KriBluesheetCreate, required = false) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1, borderBottom: '1px solid #f2f2f2' }}>
      <Typography sx={{ minWidth: 200, fontSize: '0.82rem', fontWeight: 600, color: '#333' }}>
        {label}{required && <span style={{ color: '#c62828' }}> *</span>}
      </Typography>
      <Autocomplete
        freeSolo
        fullWidth
        size="small"
        options={allUsers}
        getOptionLabel={(opt) => typeof opt === 'string' ? opt : opt.label}
        inputValue={form[field] as string ?? ''}
        onInputChange={(_, val) => set(field, val)}
        onChange={(_, val) => {
          if (val && typeof val === 'object') set(field, (val as any).value);
        }}
        renderInput={(params) => (
          <TextField {...params} placeholder="Search enrolled users…" size="small" />
        )}
      />
    </Box>
  );

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto' }}>
      {/* Breadcrumb */}
      <Box sx={{ display: 'flex', gap: 0.5, fontSize: '0.75rem', color: 'text.secondary', mb: 1.5 }}>
        <Typography
          component="span" sx={{ color: 'primary.main', fontWeight: 600, cursor: 'pointer', fontSize: '0.75rem' }}
          onClick={() => navigate('/kri-config')}
        >KRI Config</Typography>
        <Typography component="span" sx={{ fontSize: '0.75rem' }}>›</Typography>
        <Typography component="span" sx={{ fontSize: '0.75rem' }}>New KRI Onboarding</Typography>
      </Box>

      <Typography variant="h5" sx={{ fontWeight: 800, color: 'primary.main', mb: 0.5 }}>KRI Onboarding Wizard</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
        Complete all steps — a new KRI will be submitted for L3 approval upon finishing
      </Typography>

      {/* Stepper */}
      <Stepper activeStep={step} alternativeLabel sx={{ mb: 3 }}>
        {STEPS.map((label, i) => (
          <Step key={label} completed={i < step}>
            <StepLabel sx={{ '& .MuiStepLabel-label': { fontSize: '0.72rem' } }}>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {submitMutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {(submitMutation.error as any)?.response?.data?.detail || 'Submission failed. Please try again.'}
        </Alert>
      )}
      {draftMutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {(draftMutation.error as any)?.response?.data?.detail || 'Draft save failed. Please try again.'}
        </Alert>
      )}

      {/* ── Step 0 — Basic Info ─────────────────────────────── */}
      {step === 0 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 2 }}>📋 Step 1 — Basic Info</Typography>
          <Grid container spacing={2}>
            <Grid item xs={4}>{fl('KRI Code', 'kri_code', true)}</Grid>
            <Grid item xs={4}>{fl('Legacy ID', 'legacy_kri_id')}</Grid>
            <Grid item xs={4}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>Version</Typography>
              <TextField fullWidth size="small" value="1.0" disabled />
            </Grid>
            <Grid item xs={12}>{fl('KRI Name', 'kri_name', true)}</Grid>
            <Grid item xs={12}>{fl('Description', 'description', false, true)}</Grid>
          </Grid>
        </Paper>
      )}

      {/* ── Step 1 — Classification ─────────────────────────── */}
      {step === 1 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 2 }}>🏷 Step 2 — Classification</Typography>
          <Grid container spacing={2}>
            <Grid item xs={4}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>Legal Entity / Region <span style={{ color: '#c62828' }}>*</span></Typography>
              <FormControl fullWidth size="small">
                <Select value={form.region_id || ''} onChange={e => set('region_id', e.target.value)} displayEmpty>
                  <MenuItem value="">Select…</MenuItem>
                  {regions.map(r => <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>Category <span style={{ color: '#c62828' }}>*</span></Typography>
              <FormControl fullWidth size="small">
                <Select value={form.category_id || ''} onChange={e => set('category_id', e.target.value)} displayEmpty>
                  <MenuItem value="">Select…</MenuItem>
                  {categories.map(c => <MenuItem key={c.category_id} value={c.category_id}>{c.category_name}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>Risk Level <span style={{ color: '#c62828' }}>*</span></Typography>
              <FormControl fullWidth size="small">
                <Select value={form.risk_level} onChange={e => set('risk_level', e.target.value)}>
                  {['LOW','MEDIUM','HIGH','CRITICAL'].map(r => <MenuItem key={r} value={r}>{r}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>{fl('Threshold', 'threshold')}</Grid>
            <Grid item xs={4}>{fl('Circuit Breaker', 'circuit_breaker')}</Grid>
            <Grid item xs={4}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>Frequency</Typography>
              <FormControl fullWidth size="small">
                <Select value={form.frequency} onChange={e => set('frequency', e.target.value)}>
                  {['Monthly','Quarterly','Weekly','Daily'].map(f => <MenuItem key={f} value={f}>{f}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>{fl('Data Quality Objectives', 'dq_objectives', false, true)}</Grid>

            {/* ── Control IDs — checklist from DB ─────────── */}
            <Grid item xs={12}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 1 }}>
                Control IDs
              </Typography>
              {dimensions.length === 0 ? (
                <Typography variant="caption" sx={{ color: 'text.disabled' }}>No controls available.</Typography>
              ) : (
                <Grid container spacing={1}>
                  {dimensions.map((d: Dimension) => {
                    const code = d.dimension_code;
                    const checked = selectedControlIds.has(code);
                    return (
                      <Grid item xs={6} sm={4} key={d.dimension_id}>
                        <Box
                          onClick={() => toggleControlId(code)}
                          sx={{
                            display: 'flex', alignItems: 'center', gap: 1, p: 1,
                            border: '1px solid',
                            borderColor: checked ? 'primary.main' : '#e8e8e8',
                            borderRadius: 1, cursor: 'pointer',
                            bgcolor: checked ? '#e8eef5' : 'transparent',
                            transition: 'all .15s',
                            '&:hover': { borderColor: 'primary.main', bgcolor: '#f0f4fa' },
                          }}
                        >
                          <Checkbox checked={checked} size="small" sx={{ p: 0 }} onChange={() => toggleControlId(code)} />
                          <Box>
                            <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, lineHeight: 1.2 }}>
                              {d.dimension_code}
                            </Typography>
                            <Typography sx={{ fontSize: '0.70rem', color: 'text.secondary', lineHeight: 1.2 }}>
                              {d.dimension_name}
                            </Typography>
                          </Box>
                        </Box>
                      </Grid>
                    );
                  })}
                </Grid>
              )}
              {selectedControlIds.size > 0 && (
                <Typography variant="caption" sx={{ color: 'primary.main', mt: 0.5, display: 'block' }}>
                  Selected: {Array.from(selectedControlIds).join(', ')}
                </Typography>
              )}
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* ── Step 2 — Roles & Responsibilities ──────────────── */}
      {step === 2 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 1.5 }}>👥 Step 3 — Roles & Responsibilities</Typography>
          <Alert severity="info" sx={{ mb: 2, fontSize: '0.78rem' }}>
            Select from enrolled application users. You may also type a name directly if the person is not yet enrolled.
          </Alert>
          {roleRow('Primary Senior Manager', 'primary_senior_manager', true)}
          {roleRow('Metric Owner', 'metric_owner_name', true)}
          {roleRow('Remediation Owner', 'remediation_owner_name')}
          {roleRow('B&I Metrics Lead', 'bi_metrics_lead')}
          {roleRow('Data Provider', 'data_provider_name', true)}
        </Paper>
      )}

      {/* ── Step 3 — Scorecard Coverage ─────────────────────── */}
      {step === 3 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 1.5 }}>📊 Step 4 — Scorecard Coverage</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>Select all scorecards this KRI appears on:</Typography>
          <Grid container spacing={1}>
            {SCORECARD_OPTIONS.map(({ key, label }) => (
              <Grid item xs={6} key={key}>
                <Box
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1, p: 1,
                    border: '1px solid', borderColor: form[key] ? 'primary.main' : '#e8e8e8',
                    borderRadius: 1, cursor: 'pointer',
                    bgcolor: form[key] ? '#e8eef5' : 'transparent',
                    transition: 'all .15s',
                  }}
                  onClick={() => set(key, !form[key])}
                >
                  <Checkbox checked={!!form[key]} size="small" sx={{ p: 0 }} />
                  <Typography sx={{ fontSize: '0.82rem' }}>{label}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {/* ── Step 4 — Rationale & Scope ──────────────────────── */}
      {step === 4 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 2 }}>📝 Step 5 — Rationale & Scope</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12}>{fl('Why was this KRI selected?', 'why_selected', false, true)}</Grid>
            <Grid item xs={12}>{fl('Rationale for threshold including global vs local approach, UK relevance, governance', 'threshold_rationale', false, true)}</Grid>
            <Grid item xs={12}>{fl('Limitations and points for noting', 'limitations', false, true)}</Grid>
            <Grid item xs={12}>{fl('KRI Calculation and Scope', 'kri_calculation', false, true)}</Grid>
          </Grid>
        </Paper>
      )}

      {/* ── Step 5 — Runbook Upload ──────────────────────────── */}
      {step === 5 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 1.5 }}>📄 Step 6 — Runbook Upload</Typography>
          <Alert severity="info" sx={{ mb: 2, fontSize: '0.78rem' }}>
            <strong>Runbook Storage:</strong> Files are stored at <code>s3://bic-kri-runbooks/{'{region}'}/{'{kri_code}'}/</code>.
            Supported: PDF, DOCX, XLSX. Max 25 MB.
          </Alert>

          {/* Upload zone */}
          <Box
            onClick={() => fileInputRef.current?.click()}
            sx={{
              border: `2px dashed ${runbookError ? '#c62828' : runbookFile ? '#2e7d32' : '#b0c4de'}`,
              borderRadius: 2, p: 3.5, textAlign: 'center',
              bgcolor: runbookError ? '#fff5f5' : runbookFile ? '#f1f8e9' : '#f8fafd',
              cursor: 'pointer',
              '&:hover': { borderColor: 'primary.main', bgcolor: '#e8eef5' },
              transition: 'all .15s',
            }}
          >
            <input
              ref={fileInputRef} type="file" hidden
              accept=".pdf,.docx,.xlsx"
              onChange={e => handleFileSelect(e.target.files?.[0] ?? null)}
            />
            {runbookFile ? (
              <>
                <CheckIcon sx={{ fontSize: 36, color: '#2e7d32', mb: 1 }} />
                <Typography sx={{ fontWeight: 700, color: '#2e7d32' }}>{runbookFile.name}</Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {(runbookFile.size / 1024).toFixed(0)} KB — Click to replace
                </Typography>
              </>
            ) : (
              <>
                <UploadIcon sx={{ fontSize: 36, color: runbookError ? '#c62828' : '#b0c4de', mb: 1 }} />
                <Typography sx={{ fontWeight: 700, color: runbookError ? '#c62828' : 'primary.main' }}>
                  {runbookError ? 'Runbook upload is REQUIRED — please upload before proceeding' : 'Drag & drop your runbook here'}
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  or <span style={{ color: '#003366', fontWeight: 700, cursor: 'pointer' }}>browse to choose a file</span>
                </Typography>
                <Typography variant="caption" sx={{ color: '#aaa', display: 'block', mt: 0.5 }}>
                  PDF · DOCX · XLSX | Max 25 MB · <span style={{ color: '#c62828', fontWeight: 700 }}>Required *</span>
                </Typography>
              </>
            )}
          </Box>

          <Divider sx={{ my: 2 }} />
          <Grid container spacing={2}>
            <Grid item xs={6}>{fl('Runbook Version', 'runbook_version')}</Grid>
            <Grid item xs={6}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#444', mb: 0.5 }}>Last Review Date</Typography>
              <TextField
                fullWidth size="small" type="date"
                value={form.runbook_review_date || ''}
                onChange={e => set('runbook_review_date', e.target.value || '')}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12}>{fl('Notes', 'runbook_notes', false, true)}</Grid>
          </Grid>
        </Paper>
      )}

      {/* ── Step 6 — Review & Submit ─────────────────────────── */}
      {step === 6 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 1.5 }}>✅ Step 7 — Review & Submit</Typography>
          <Alert severity="info" sx={{ mb: 2, fontSize: '0.78rem' }}>
            Review all details below before submitting. Once submitted, this KRI will be created with status <strong>PENDING APPROVAL</strong> and the L3 Admin will be notified.
          </Alert>

          {[
            { heading: 'Basic Info', rows: [
              ['KRI Code', form.kri_code], ['Legacy ID', form.legacy_kri_id||'—'],
              ['KRI Name', form.kri_name], ['Description', form.description||'—'],
            ]},
            { heading: 'Classification', rows: [
              ['Region', regions.find(r => r.region_id === Number(form.region_id))?.region_name || '—'],
              ['Category', categories.find(c => c.category_id === Number(form.category_id))?.category_name || '—'],
              ['Risk Level', form.risk_level], ['Frequency', form.frequency],
              ['Threshold', form.threshold||'—'], ['Circuit Breaker', form.circuit_breaker||'—'],
              ['Control IDs', form.control_ids || '—'],
            ]},
            { heading: 'Roles & Responsibilities', rows: [
              ['Primary Senior Manager', form.primary_senior_manager||'—'],
              ['Metric Owner', form.metric_owner_name||'—'],
              ['Remediation Owner', form.remediation_owner_name||'—'],
              ['B&I Metrics Lead', form.bi_metrics_lead||'—'],
              ['Data Provider', form.data_provider_name||'—'],
            ]},
            { heading: 'Runbook', rows: [
              ['File', runbookFile ? runbookFile.name : '—'],
              ['Version', form.runbook_version||'v1.0'],
            ]},
          ].map(section => (
            <Box key={section.heading} sx={{ mb: 2 }}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'primary.main', textTransform: 'uppercase', letterSpacing: .5, mb: 0.8, pb: 0.5, borderBottom: '2px solid #e8eef5' }}>
                {section.heading}
              </Typography>
              <Grid container spacing={0.5}>
                {section.rows.map(([k, v]) => (
                  <React.Fragment key={k}>
                    <Grid item xs={4}><Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>{k}</Typography></Grid>
                    <Grid item xs={8}><Typography variant="body2">{v}</Typography></Grid>
                  </React.Fragment>
                ))}
              </Grid>
            </Box>
          ))}
        </Paper>
      )}

      {/* ── Nav buttons ──────────────────────────────────────── */}
      <Paper sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, mt: 2 }}>
        <Button variant="outlined" disabled={step === 0} onClick={() => setStep(s => s - 1)}>← Back</Button>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>Step {step + 1} of {STEPS.length}</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            disabled={draftMutation.isPending}
            startIcon={draftMutation.isPending ? <CircularProgress size={14} color="inherit" /> : null}
            onClick={() => draftMutation.mutate(form)}
          >
            {draftKriId ? 'Update Draft & Exit' : 'Save Draft & Exit'}
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={submitMutation.isPending}
            startIcon={submitMutation.isPending ? <CircularProgress size={14} color="inherit" /> : null}
          >
            {step === STEPS.length - 1 ? '🚀 Submit for Approval' : 'Next →'}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
