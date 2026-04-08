import React from 'react';
import { Box, FormControl, InputLabel, Select, MenuItem, Typography } from '@mui/material';
import { useAppDispatch, useAppSelector, setPeriod, setRegion } from '../../store';
import { getAvailablePeriods } from '../../utils/helpers';
import type { Region } from '../../types';

interface GlobalFilterToolbarProps {
  regions: Region[];
}

export default function GlobalFilterToolbar({ regions }: GlobalFilterToolbarProps) {
  const dispatch = useAppDispatch();
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const periods = getAvailablePeriods(12);

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 3,
        px: 2,
        py: 1.5,
        alignItems: 'center',
        flexWrap: 'wrap',
        backgroundColor: '#fafafa',
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Period Filter */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            color: 'text.secondary',
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            minWidth: 50,
          }}
        >
          Period
        </Typography>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <Select
            value={`${selectedPeriod.year}-${selectedPeriod.month}`}
            onChange={(e) => {
              const [y, m] = e.target.value.split('-').map(Number);
              dispatch(setPeriod({ year: y, month: m }));
            }}
            sx={{ fontSize: '0.8rem', fontWeight: 500 }}
          >
            {periods.map((p) => (
              <MenuItem key={`${p.year}-${p.month}`} value={`${p.year}-${p.month}`}>
                {p.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* Region Filter */}
      <FormControl size="small" sx={{ minWidth: 140 }}>
        <InputLabel sx={{ fontSize: '0.8rem' }}>Region</InputLabel>
        <Select
          displayEmpty
          value={selectedRegionId ?? ''}
          label="Region"
          onChange={(e) => dispatch(setRegion(e.target.value === '' ? null : Number(e.target.value)))}
          sx={{ fontSize: '0.8rem' }}
        >
          <MenuItem value="">All Regions</MenuItem>
          {regions.map((r) => (
            <MenuItem key={r.region_id} value={r.region_id}>
              {r.region_name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}
