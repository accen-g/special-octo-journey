import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, Stepper, Step, StepLabel,
  Button, TextField, Select, MenuItem, FormControl, InputLabel,
  Grid, Chip, Alert, CircularProgress,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { kriApi, lookupApi } from '../../api/client';
import type { Region, Category, Dimension } from '../../types';

const steps = ['Basic Info', 'Control Dimensions', 'Assignments', 'Data Sources', 'Review'];

export default function KriWizardPage() {
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState({
    kri_code: '', kri_name: '', description: '', category_id: '', region_id: '',
    risk_level: 'MEDIUM', framework: '', dimensions: [] as any[], assignments: [] as any[], data_sources: [] as any[],
  });
  const [success, setSuccess] = useState(false);

  const { data: regions = [] } = useQuery<Region[]>({ queryKey: ['regions'], queryFn: () => lookupApi.regions().then(r => r.data) });
  const { data: categories = [] } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: () => lookupApi.categories().then(r => r.data) });
  const { data: dimensions = [] } = useQuery<Dimension[]>({ queryKey: ['dimensions'], queryFn: () => lookupApi.dimensions().then(r => r.data) });

  const onboardMutation = useMutation({
    mutationFn: (data: any) => kriApi.onboard(data),
    onSuccess: () => setSuccess(true),
  });

  const handleNext = () => {
    if (activeStep === steps.length - 1) {
      onboardMutation.mutate({
        ...formData,
        category_id: Number(formData.category_id),
        region_id: Number(formData.region_id),
      });
    } else {
      setActiveStep((s) => s + 1);
    }
  };

  if (success) {
    return (
      <Box sx={{ maxWidth: 600, mx: 'auto', mt: 4 }}>
        <Alert severity="success" sx={{ mb: 2 }}>
          KRI onboarded successfully! The KRI is now active and ready for monthly tracking.
        </Alert>
        <Button variant="contained" onClick={() => { setSuccess(false); setActiveStep(0); setFormData({ kri_code: '', kri_name: '', description: '', category_id: '', region_id: '', risk_level: 'MEDIUM', framework: '', dimensions: [], assignments: [], data_sources: [] }); }}>
          Onboard Another KRI
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>KRI Onboarding Wizard</Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}><StepLabel>{label}</StepLabel></Step>
        ))}
      </Stepper>

      <Card sx={{ maxWidth: 800, mx: 'auto' }}>
        <CardContent>
          {activeStep === 0 && (
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField label="KRI Code" fullWidth size="small" required value={formData.kri_code}
                  onChange={(e) => setFormData({ ...formData, kri_code: e.target.value })} />
              </Grid>
              <Grid item xs={6}>
                <TextField label="KRI Name" fullWidth size="small" required value={formData.kri_name}
                  onChange={(e) => setFormData({ ...formData, kri_name: e.target.value })} />
              </Grid>
              <Grid item xs={12}>
                <TextField label="Description" fullWidth multiline rows={2} size="small" value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
              </Grid>
              <Grid item xs={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Category</InputLabel>
                  <Select value={formData.category_id} label="Category"
                    onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}>
                    {categories.map((c) => <MenuItem key={c.category_id} value={c.category_id}>{c.category_name}</MenuItem>)}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Region</InputLabel>
                  <Select value={formData.region_id} label="Region"
                    onChange={(e) => setFormData({ ...formData, region_id: e.target.value })}>
                    {regions.map((r) => <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>)}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Risk Level</InputLabel>
                  <Select value={formData.risk_level} label="Risk Level"
                    onChange={(e) => setFormData({ ...formData, risk_level: e.target.value })}>
                    {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12}>
                <TextField label="Framework" fullWidth size="small" value={formData.framework}
                  onChange={(e) => setFormData({ ...formData, framework: e.target.value })} />
              </Grid>
            </Grid>
          )}

          {activeStep === 1 && (
            <Box>
              <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                Configure SLA and thresholds for each control dimension.
              </Typography>
              {dimensions.map((dim) => (
                <Box key={dim.dimension_id} sx={{ display: 'flex', gap: 2, mb: 1.5, alignItems: 'center' }}>
                  <Chip label={dim.dimension_name} sx={{ minWidth: 180, fontWeight: 600 }} />
                  <TextField label="SLA Days" type="number" size="small" defaultValue={3} sx={{ width: 100 }} />
                  <TextField label="Variance %" type="number" size="small" defaultValue={10} sx={{ width: 100 }} />
                </Box>
              ))}
            </Box>
          )}

          {activeStep === 2 && (
            <Alert severity="info">
              Assignments will be configured after KRI creation. You can assign users to specific dimensions and roles from the Admin panel.
            </Alert>
          )}

          {activeStep === 3 && (
            <Alert severity="info">
              Data source mappings can be configured after KRI creation. Supports DATABASE, FILE, API, and MANUAL source types.
            </Alert>
          )}

          {activeStep === 4 && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Review & Confirm</Typography>
              <Grid container spacing={1}>
                {[
                  ['KRI Code', formData.kri_code],
                  ['KRI Name', formData.kri_name],
                  ['Category', categories.find(c => c.category_id === Number(formData.category_id))?.category_name || ''],
                  ['Region', regions.find(r => r.region_id === Number(formData.region_id))?.region_name || ''],
                  ['Risk Level', formData.risk_level],
                  ['Framework', formData.framework || '—'],
                ].map(([label, value]) => (
                  <React.Fragment key={label}>
                    <Grid item xs={4}><Typography variant="body2" sx={{ fontWeight: 700, color: 'text.secondary' }}>{label}</Typography></Grid>
                    <Grid item xs={8}><Typography variant="body2">{value}</Typography></Grid>
                  </React.Fragment>
                ))}
              </Grid>
            </Box>
          )}

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
            <Button disabled={activeStep === 0} onClick={() => setActiveStep((s) => s - 1)}>Back</Button>
            <Button variant="contained" onClick={handleNext} disabled={onboardMutation.isPending}>
              {activeStep === steps.length - 1 ? (onboardMutation.isPending ? 'Creating...' : 'Create KRI') : 'Next'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
