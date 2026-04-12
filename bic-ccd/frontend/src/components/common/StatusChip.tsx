import React from 'react';
import { Chip } from '@mui/material';
import { statusConfig } from '../../utils/helpers';

interface StatusChipProps {
  status: string;
  size?: 'small' | 'medium';
}

/**
 * Single source of truth for all status chip rendering across the app.
 * Covers: control statuses, approval workflow statuses, KRI config statuses,
 * scorecard statuses, and user active/inactive states.
 * Falls back to a neutral grey chip for unknown status strings.
 */
export default function StatusChip({ status, size = 'small' }: StatusChipProps) {
  const cfg = statusConfig[status];
  if (!cfg) {
    return (
      <Chip
        label={status}
        size={size}
        sx={{ bgcolor: '#f0f0f0', color: '#555', fontWeight: 600, fontSize: '0.72rem' }}
      />
    );
  }
  return (
    <Chip
      label={cfg.label}
      size={size}
      sx={{
        bgcolor: cfg.bg,
        color: cfg.color,
        fontWeight: 700,
        fontSize: size === 'small' ? '0.72rem' : '0.82rem',
        border: `1px solid ${cfg.color}25`,
      }}
    />
  );
}
