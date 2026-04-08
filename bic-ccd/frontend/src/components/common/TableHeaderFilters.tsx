import React from 'react';
import { TableRow, TableCell, TextField, Select, MenuItem, Box } from '@mui/material';

interface FilterConfig {
  key: string;
  label: string;
  type: 'text' | 'select';
  options?: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
  width?: string;
}

interface TableHeaderFiltersProps {
  filters: FilterConfig[];
  borderStyle?: { borderRight?: string };
}

export default function TableHeaderFilters({ filters, borderStyle }: TableHeaderFiltersProps) {
  return (
    <TableRow
      sx={{
        backgroundColor: '#fafafa',
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      {filters.map((filter) => (
        <TableCell
          key={filter.key}
          sx={{
            py: 1,
            px: 1,
            ...(borderStyle || { borderRight: '1px solid rgba(0,0,0,0.07)' }),
            '&:last-child': { borderRight: 'none' },
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', minHeight: 36 }}>
            {filter.type === 'text' ? (
              <TextField
                type="text"
                placeholder={`Search ${filter.label}...`}
                size="small"
                value={filter.value}
                onChange={(e) => filter.onChange(e.target.value)}
                sx={{
                  width: '100%',
                  '& .MuiOutlinedInput-root': {
                    fontSize: '0.8rem',
                    height: 32,
                  },
                  '& .MuiOutlinedInput-input::placeholder': {
                    opacity: 0.6,
                  },
                }}
              />
            ) : (
              <Select
                size="small"
                displayEmpty
                value={filter.value}
                onChange={(e) => filter.onChange(e.target.value)}
                sx={{
                  width: '100%',
                  fontSize: '0.8rem',
                  height: 32,
                }}
              >
                <MenuItem value="">All</MenuItem>
                {filter.options?.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
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
