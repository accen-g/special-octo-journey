import React from 'react';
import { Box, Select, MenuItem, Chip, FormControl, InputLabel, Typography } from '@mui/material';
import { useAppSelector, useAppDispatch, setPeriod, setRegion } from '../../store';
import { getAvailablePeriods, formatPeriod } from '../../utils/helpers';
import type { Region } from '../../types';

interface FilterBarProps {
  regions: Region[];
}

export default function FilterBar({ regions }: FilterBarProps) {
  const dispatch = useAppDispatch();
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const periods = getAvailablePeriods(12);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.8rem' }}>
          PERIOD
        </Typography>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <Select
            value={`${selectedPeriod.year}-${selectedPeriod.month}`}
            onChange={(e) => {
              const [y, m] = e.target.value.split('-').map(Number);
              dispatch(setPeriod({ year: y, month: m }));
            }}
            sx={{ fontSize: '0.82rem', fontWeight: 500 }}
          >
            {periods.map((p) => (
              <MenuItem key={`${p.year}-${p.month}`} value={`${p.year}-${p.month}`}>
                {p.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      <FormControl size="small" sx={{ minWidth: 130 }}>
        <Select
          displayEmpty
          value={selectedRegionId ?? ''}
          onChange={(e) => dispatch(setRegion(e.target.value === '' ? null : Number(e.target.value)))}
          sx={{ fontSize: '0.82rem' }}
        >
          <MenuItem value="">All Regions</MenuItem>
          {regions.map((r) => (
            <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Active filter chips */}
      {selectedRegionId && (
        <Chip
          label={`${regions.find(r => r.region_id === selectedRegionId)?.region_code || 'Region'}`}
          onDelete={() => dispatch(setRegion(null))}
          size="small"
          sx={{ bgcolor: '#ebf5fb', color: '#2471a3', fontWeight: 600, fontSize: '0.75rem' }}
        />
      )}

      <Box sx={{ ml: 'auto' }}>
        <Typography variant="body2" sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
          Last updated: {new Date().toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>
    </Box>
  );
}
