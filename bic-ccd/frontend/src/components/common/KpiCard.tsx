import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface KpiCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  detail?: string;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  borderColor?: string;
  alert?: boolean;
  onClick?: () => void;
}

export default function KpiCard({
  title, value, subtitle, detail, trend, trendDirection, borderColor, alert, onClick,
}: KpiCardProps) {
  return (
    <Card
      onClick={onClick}
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        borderLeft: `4px solid ${borderColor || '#003366'}`,
        borderColor: alert ? '#c0392b' : undefined,
        border: alert ? '2px solid #c0392b' : undefined,
        borderLeftWidth: alert ? undefined : 4,
        transition: 'all 0.2s',
        '&:hover': onClick ? { transform: 'translateY(-2px)', boxShadow: 3 } : {},
        height: '100%',
      }}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography variant="body2" sx={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: 'text.secondary', mb: 0.5 }}>
          {title}
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 800, color: borderColor || 'primary.main', lineHeight: 1.2 }}>
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="body2" sx={{ mt: 0.5, fontSize: '0.78rem', color: 'text.secondary' }}>
            {subtitle}
          </Typography>
        )}
        {trend && (
          <Typography
            variant="body2"
            sx={{
              mt: 0.3,
              fontSize: '0.72rem',
              fontWeight: 600,
              color: trendDirection === 'up' ? '#c0392b' : trendDirection === 'down' ? '#27ae60' : '#7f8c8d',
            }}
          >
            {trendDirection === 'up' ? '▲' : trendDirection === 'down' ? '▼' : '–'} {trend}
          </Typography>
        )}
        {detail && (
          <Typography variant="body2" sx={{ mt: 0.3, fontSize: '0.72rem', color: alert ? '#c0392b' : 'primary.main', fontWeight: 600 }}>
            {alert ? '▲ ' : ''}{detail}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
