import React, { useState, useRef } from 'react';
import {
  Box, Card, CardContent, Typography, Button, Chip, IconButton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Grid, Select, MenuItem, FormControl, InputLabel,
} from '@mui/material';
import { CloudUpload, Lock, Download, Visibility, Description } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { evidenceApi, lookupApi, kriApi } from '../../api/client';
import { useAppSelector } from '../../store';
import { hasRole } from '../../utils/helpers';
import FilterBar from '../../components/common/FilterBar';
import type { Region, Dimension } from '../../types';

const fileTypeIcons: Record<string, string> = {
  xlsx: '📊', pdf: '📄', pptx: '📽', msg: '✉', csv: '📋', docx: '📝',
};

export default function EvidencePage() {
  const queryClient = useQueryClient();
  const { user } = useAppSelector((s) => s.auth);
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadKriId, setUploadKriId] = useState<number | ''>('');
  const [uploadDimId, setUploadDimId] = useState<number | ''>('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  // KRIs filtered by the currently selected region (for upload dialog)
  const { data: krisData } = useQuery({
    queryKey: ['kris-for-upload', selectedRegionId],
    queryFn: () => kriApi.list({ region_id: selectedRegionId || undefined, page_size: 200 }).then((r) => r.data),
    enabled: uploadOpen,
  });
  const uploadableKris: any[] = krisData?.items || [];

  // Check if user can upload evidence (L1, L2, L3_ADMIN, DATA_PROVIDER, SYSTEM_ADMIN)
  const canUploadEvidence = hasRole(user?.roles || [], ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'DATA_PROVIDER', 'SYSTEM_ADMIN']);

  const { data: regions = [] } = useQuery<Region[]>({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: dimensions = [] } = useQuery<Dimension[]>({
    queryKey: ['dimensions'],
    queryFn: () => lookupApi.dimensions().then((r) => r.data),
  });

  const { data, isLoading } = useQuery({
    queryKey: ['evidence', selectedPeriod, selectedRegionId],
    queryFn: () => evidenceApi.list({
      year: selectedPeriod.year, month: selectedPeriod.month,
      region_id: selectedRegionId || undefined,
    }).then((r) => r.data),
  });

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const results = [];
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('kri_id', String(uploadKriId));
        fd.append('dimension_id', String(uploadDimId));
        fd.append('year', String(selectedPeriod.year));
        fd.append('month', String(selectedPeriod.month));
        const res = await evidenceApi.upload(fd);
        results.push(res.data);
      }
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evidence'] });
      setUploadOpen(false);
      setUploadKriId('');
      setUploadDimId('');
      setSelectedFiles([]);
    },
  });

  const lockMutation = useMutation({
    mutationFn: (id: number) => evidenceApi.lock(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evidence'] }),
  });

  const items = data?.items || [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>Evidence Vault</Typography>
        {canUploadEvidence && (
          <Button
            variant="contained"
            startIcon={<CloudUpload />}
            onClick={() => setUploadOpen(true)}
          >
            Upload Evidence
          </Button>
        )}
      </Box>

      <FilterBar regions={regions} />

      <Card>
        <CardContent sx={{ p: 0 }}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
          ) : items.length === 0 ? (
            <Alert severity="info" sx={{ m: 2 }}>No evidence files for this period. Upload evidence to get started.</Alert>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>File Name</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>KRI</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Version</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Uploaded</TableCell>
                    <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {items.map((ev: any) => (
                    <TableRow key={ev.evidence_id} hover>
                      <TableCell>
                        <Typography sx={{ fontSize: '1.2rem' }}>{fileTypeIcons[ev.file_type] || '📎'}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography sx={{ fontSize: '0.82rem', fontWeight: 500 }}>{ev.file_name}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography sx={{ fontSize: '0.78rem' }}>{ev.kri_name}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={`v${ev.version_number}`} size="small" variant="outlined" sx={{ fontWeight: 700, fontSize: '0.7rem' }} />
                      </TableCell>
                      <TableCell>
                        {ev.is_locked ? (
                          <Chip icon={<Lock sx={{ fontSize: 14 }} />} label="Locked" size="small"
                            sx={{ bgcolor: '#fdecea', color: '#922b21', fontWeight: 600, fontSize: '0.7rem' }} />
                        ) : (
                          <Chip label="Open" size="small"
                            sx={{ bgcolor: '#e8f8f0', color: '#1e8449', fontWeight: 600, fontSize: '0.7rem' }} />
                        )}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.78rem' }}>
                        {new Date(ev.uploaded_dt).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </TableCell>
                      <TableCell align="center">
                        <IconButton size="small" title="View"><Visibility fontSize="small" /></IconButton>
                        {!ev.is_locked && (
                          <IconButton
                            size="small"
                            title="Lock"
                            onClick={() => lockMutation.mutate(ev.evidence_id)}
                          >
                            <Lock fontSize="small" />
                          </IconButton>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* ─── Upload Dialog ────────────────────────────────── */}
      <Dialog open={uploadOpen} onClose={() => setUploadOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Upload Evidence</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>KRI</InputLabel>
                <Select
                  value={uploadKriId}
                  label="KRI"
                  onChange={(e) => setUploadKriId(Number(e.target.value))}
                >
                  {uploadableKris.length === 0 && (
                    <MenuItem disabled value="">
                      {selectedRegionId ? 'No KRIs for selected region' : 'No KRIs available'}
                    </MenuItem>
                  )}
                  {uploadableKris.map((k: any) => (
                    <MenuItem key={k.kri_id} value={k.kri_id}>
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.82rem' }}>{k.kri_name}</Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>{k.kri_code}</Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Dimension</InputLabel>
                <Select
                  value={uploadDimId}
                  label="Dimension"
                  onChange={(e) => setUploadDimId(Number(e.target.value))}
                >
                  {dimensions.map((d) => (
                    <MenuItem key={d.dimension_id} value={d.dimension_id}>{d.dimension_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".xlsx,.pdf,.pptx,.msg,.csv,.docx"
                style={{ display: 'none' }}
                onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))}
              />
              <Button
                fullWidth
                variant="outlined"
                startIcon={<CloudUpload />}
                onClick={() => fileRef.current?.click()}
                sx={{ py: 2, borderStyle: 'dashed' }}
              >
                {selectedFiles.length > 0
                  ? `${selectedFiles.length} file(s) selected`
                  : 'Click to select files (xlsx, pdf, pptx, msg, csv, docx)'}
              </Button>
              {selectedFiles.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  {selectedFiles.map((f, i) => (
                    <Chip key={i} label={f.name} size="small" sx={{ mr: 0.5, mb: 0.5, fontSize: '0.72rem' }} />
                  ))}
                </Box>
              )}
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUploadOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => uploadMutation.mutate(selectedFiles)}
            disabled={!uploadKriId || !uploadDimId || selectedFiles.length === 0 || uploadMutation.isPending}
          >
            {uploadMutation.isPending ? 'Uploading...' : 'Upload'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
