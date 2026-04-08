import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Typography,
  Tooltip,
} from '@mui/material';
import { useAppSelector, useAppDispatch, setPeriod, setRegion } from '../../store';
import { getAvailablePeriods } from '../../utils/helpers';
import type { Region } from '../../types';

interface HeaderFiltersProps {
  regions: Region[];
  categories: any[];
  viewMode: 'controls' | 'kris';
  categoryFilter?: string;
  onCategoryChange?: (category: string) => void;
}

export default function HeaderFilters({
  regions,
  categories,
  viewMode,
  categoryFilter = '',
  onCategoryChange,
}: HeaderFiltersProps) {
  const dispatch = useAppDispatch();
  const { selectedPeriod, selectedRegionId } = useAppSelector((s) => s.ui);
  const periods = getAvailablePeriods(12);

  const hasActiveFilters = categoryFilter;

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        px: 2,
        py: 1.5,
        alignItems: 'center',
        flexWrap: 'wrap',
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: '#fafafa',
      }}
    >
      {/* Period Filter */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem', textTransform: 'uppercase' }}>
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

      {/* Category Filter (visible only in KRI View) */}
      {viewMode === 'kris' && (
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel sx={{ fontSize: '0.8rem' }}>Category</InputLabel>
          <Select
            displayEmpty
            value={categoryFilter}
            label="Category"
            onChange={(e) => onCategoryChange?.(e.target.value)}
            sx={{ fontSize: '0.8rem' }}
          >
            <MenuItem value="">All Categories</MenuItem>
            {categories.map((c: any) => (
              <MenuItem key={c.category_id} value={c.category_name}>
                {c.category_name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {/* Clear Filters Button */}
      {hasActiveFilters && (
        <Tooltip title="Clear category filter">
          <Button
            size="small"
            variant="text"
            sx={{ fontSize: '0.75rem', color: 'text.secondary' }}
            onClick={() => {
              onCategoryChange?.('');
            }}
          >
            Clear
          </Button>
        </Tooltip>
      )}

      {/* Filter Status */}
      {categoryFilter && (
        <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
          Category: {categoryFilter} (filtered)
        </Typography>
      )}
    </Box>
  );
}
