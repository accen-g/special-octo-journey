import React from 'react';
import { Chip, Box, Typography } from '@mui/material';
import { statusConfig, ragConfig } from '../../utils/helpers';

interface StatusBadgeProps {
  status: string;
  type?: 'status' | 'rag';
  size?: 'small' | 'medium';
}

export default function StatusBadge({ status, type = 'status', size = 'small' }: StatusBadgeProps) {
  const config = type === 'rag' ? ragConfig[status] : statusConfig[status];
  if (!config) return <Chip label={status} size={size} />;

  return (
    <Chip
      size={size}
      label={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography component="span" sx={{ fontSize: size === 'small' ? '0.7rem' : '0.85rem', lineHeight: 1 }}>
            {config.icon}
          </Typography>
          <Typography component="span" sx={{ fontSize: size === 'small' ? '0.72rem' : '0.82rem', fontWeight: 600 }}>
            {config.label}
          </Typography>
        </Box>
      }
      sx={{
        bgcolor: config.bg,
        color: config.color,
        border: `1px solid ${config.color}25`,
        fontWeight: 600,
      }}
      aria-label={`Status: ${config.label}`}
    />
  );
}
