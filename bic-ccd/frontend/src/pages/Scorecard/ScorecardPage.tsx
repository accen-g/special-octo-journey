import React from 'react';
import { Box, Typography, Card, CardContent, Alert } from '@mui/material';

export default function ScorecardPage() {
  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>Scorecard</Typography>
      <Card>
        <CardContent>
          <Alert severity="info">
            The Scorecard module provides a consolidated view of KRI health across all regions and categories.
            It aggregates monthly control execution data, SLA compliance metrics, and evidence completeness
            into a single summary view for executive reporting.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
}
