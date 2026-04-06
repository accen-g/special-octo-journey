import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, TextField, Button,
  Alert, CircularProgress, Select, MenuItem, FormControl, InputLabel,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../api/client';
import { useAppDispatch } from '../../store';
import { loginSuccess } from '../../store';

const demoUsers = [
  { soe_id: 'RANREDDY', label: 'Rahul Anreddy — Management' },
  { soe_id: 'JSMITH01', label: 'John Smith — L1 Approver' },
  { soe_id: 'ALEE02', label: 'Angela Lee — L2 Approver' },
  { soe_id: 'BWILSON', label: 'Brian Wilson — L3 Admin' },
  { soe_id: 'DPATEL', label: 'Deepa Patel — Data Provider' },
  { soe_id: 'MKUMAR', label: 'Manoj Kumar — Metric Owner' },
  { soe_id: 'SYSADMIN', label: 'System Admin' },
];

export default function LoginPage() {
  const [soeId, setSoeId] = useState('');
  const [password, setPassword] = useState('demo');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const handleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await authApi.login(soeId, password);
      dispatch(loginSuccess({ user: res.data.user, token: res.data.access_token }));
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      bgcolor: '#f0f2f5',
      backgroundImage: 'linear-gradient(135deg, #003366 0%, #1a5276 50%, #2471a3 100%)',
    }}>
      <Card sx={{ width: 420, p: 1 }}>
        <CardContent>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Box sx={{
              width: 56, height: 56, borderRadius: 2, bgcolor: '#003366', color: '#fff',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 800, fontSize: 18, mb: 1.5,
            }}>
              BIC
            </Box>
            <Typography variant="h5" sx={{ fontWeight: 700, color: '#003366' }}>
              B&I Data Metrics and Controls
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
              BIC-CCD — Enterprise KRI Platform
            </Typography>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Quick Login (Demo Users)</InputLabel>
            <Select
              value={soeId}
              label="Quick Login (Demo Users)"
              onChange={(e) => setSoeId(e.target.value)}
            >
              {demoUsers.map((u) => (
                <MenuItem key={u.soe_id} value={u.soe_id}>{u.label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary', my: 1.5, fontSize: '0.78rem' }}>
            — or enter manually —
          </Typography>

          <TextField
            label="SOE ID"
            fullWidth
            value={soeId}
            onChange={(e) => setSoeId(e.target.value)}
            sx={{ mb: 2 }}
            size="small"
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{ mb: 3 }}
            size="small"
            helperText="Any password accepted in demo mode"
          />
          <Button
            fullWidth
            variant="contained"
            size="large"
            onClick={handleLogin}
            disabled={!soeId || loading}
            sx={{ py: 1.2, fontWeight: 700 }}
          >
            {loading ? <CircularProgress size={22} color="inherit" /> : 'Sign In'}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}
