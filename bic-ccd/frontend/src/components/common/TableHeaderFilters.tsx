/**
 * TableHeaderFilters — reusable inline column filter row.
 *
 * Features:
 *  - Text inputs: debounced 300 ms, clear (×) button when non-empty
 *  - Select inputs: instant update, "All" as default empty option
 *  - type: 'none' → empty cell (spacer for icon/action columns)
 *
 * Named exports:
 *  - SortHeader  — drop-in <TableSortLabel> wrapper for column headers
 *
 * Default export:
 *  - TableHeaderFilters — the filter row <TableRow>
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  TableRow, TableCell, TextField, Select, MenuItem,
  Box, IconButton, InputAdornment, TableSortLabel,
} from '@mui/material';
import { Clear } from '@mui/icons-material';

// ─── Types ────────────────────────────────────────────────────

export interface FilterConfig {
  key: string;
  label: string;
  type: 'text' | 'select' | 'none';
  options?: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
  width?: string | number;
}

export interface TableHeaderFiltersProps {
  filters: FilterConfig[];
  borderStyle?: { borderRight?: string };
}

// ─── SortHeader (named export) ────────────────────────────────

export interface SortHeaderProps {
  label: string;
  field: string;
  sortKey: string | null;
  sortDir: 'asc' | 'desc';
  onSort: (field: string) => void;
  sx?: object;
}

/** Drop-in wrapper for MUI TableSortLabel — use inside a <TableCell>. */
export function SortHeader({ label, field, sortKey, sortDir, onSort, sx }: SortHeaderProps) {
  return (
    <TableSortLabel
      active={sortKey === field}
      direction={sortKey === field ? sortDir : 'asc'}
      onClick={() => onSort(field)}
      sx={{
        fontSize: 'inherit',
        fontWeight: 'inherit',
        whiteSpace: 'nowrap',
        '& .MuiTableSortLabel-icon': { fontSize: 14, opacity: sortKey === field ? 1 : 0.35 },
        ...sx,
      }}
    >
      {label}
    </TableSortLabel>
  );
}

// ─── Debounced text input with clear button ───────────────────

interface DebouncedTextProps {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  width?: string | number;
}

function DebouncedText({ value, onChange, placeholder, width }: DebouncedTextProps) {
  const [local, setLocal] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync when parent resets the filter (e.g., "Clear all")
  useEffect(() => {
    setLocal(value);
  }, [value]);

  const emit = (v: string) => {
    setLocal(v);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(v), 300);
  };

  return (
    <TextField
      size="small"
      placeholder={placeholder}
      value={local}
      onChange={(e) => emit(e.target.value)}
      sx={{
        width: width ?? '100%',
        '& .MuiOutlinedInput-root': { fontSize: '0.78rem', height: 30 },
        '& .MuiOutlinedInput-input': { py: 0.5, px: 1 },
        '& .MuiOutlinedInput-input::placeholder': { opacity: 0.55, fontSize: '0.76rem' },
      }}
      InputProps={{
        endAdornment: local ? (
          <InputAdornment position="end" sx={{ mr: -0.5 }}>
            <IconButton
              size="small"
              onClick={() => emit('')}
              edge="end"
              tabIndex={-1}
              sx={{ p: 0.25 }}
            >
              <Clear sx={{ fontSize: 13, color: 'text.disabled' }} />
            </IconButton>
          </InputAdornment>
        ) : undefined,
      }}
    />
  );
}

// ─── Main component ───────────────────────────────────────────

export default function TableHeaderFilters({ filters, borderStyle }: TableHeaderFiltersProps) {
  const cellBorder = borderStyle ?? { borderRight: '1px solid rgba(0,0,0,0.07)' };

  return (
    <TableRow sx={{ backgroundColor: '#fafafa', borderBottom: '1px solid', borderColor: 'divider' }}>
      {filters.map((filter) => (
        <TableCell
          key={filter.key}
          sx={{
            py: 0.75,
            px: 0.75,
            ...cellBorder,
            '&:last-child': { borderRight: 'none' },
            ...(filter.width ? { width: filter.width } : {}),
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', minHeight: 30 }}>
            {filter.type === 'none' ? null : filter.type === 'text' ? (
              <DebouncedText
                value={filter.value}
                onChange={filter.onChange}
                placeholder={`Search ${filter.label}…`}
                width={filter.width}
              />
            ) : (
              <Select
                size="small"
                displayEmpty
                value={filter.value}
                onChange={(e) => filter.onChange(e.target.value as string)}
                sx={{
                  width: '100%',
                  fontSize: '0.78rem',
                  height: 30,
                  '& .MuiSelect-select': { py: 0.5, px: 1 },
                }}
              >
                <MenuItem value="" sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  All
                </MenuItem>
                {filter.options?.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: '0.8rem' }}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            )}
          </Box>
        </TableCell>
      ))}
    </TableRow>
  );
}
