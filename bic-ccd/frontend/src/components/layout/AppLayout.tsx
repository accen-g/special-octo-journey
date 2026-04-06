import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar, Toolbar, Typography, IconButton, Drawer, List, ListItemButton,
  ListItemIcon, ListItemText, Box, Chip, Badge, Avatar, Menu, MenuItem,
  Divider, Tooltip, useMediaQuery, useTheme,
} from '@mui/material';
import {
  Dashboard as DashboardIcon, TableChart, Approval, CloudUpload,
  TrendingUp, Settings, PersonAdd, Menu as MenuIcon, Notifications,
  Logout, ChevronLeft, Assessment, Warning, Speed,
} from '@mui/icons-material';
import { useAppSelector, useAppDispatch, logout, setActiveRole } from '../../store';
import { roleLabel, statusConfig, hasRole, getNavSectionsForRole } from '../../utils/helpers';
import type { RoleCode } from '../../types';

const DRAWER_WIDTH = 220;

const navSections = [
  {
    label: 'OVERVIEW',
    items: [{ label: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' }],
  },
  {
    label: 'CONTROLS',
    items: [
      { label: 'Data Control', icon: <TableChart />, path: '/data-control', badge: true },
      { label: 'Approvals', icon: <Approval />, path: '/approvals' },
    ],
  },
  {
    label: 'REPORTS',
    items: [
      { label: 'Scorecard', icon: <Assessment />, path: '/scorecard' },
      { label: 'Evidence', icon: <CloudUpload />, path: '/evidence' },
      { label: 'Variance', icon: <TrendingUp />, path: '/variance' },
      { label: 'Escalation Metrics', icon: <Warning />, path: '/escalation-metrics' },
    ],
  },
  {
    label: 'ADMINISTRATION',
    items: [
      { label: 'KRI Wizard', icon: <Speed />, path: '/kri-wizard' },
      { label: 'Admin', icon: <Settings />, path: '/admin' },
    ],
  },
];

export default function AppLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [open, setOpen] = useState(!isMobile);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector((s) => s.auth);
  const { activeRole } = useAppSelector((s) => s.ui);

  const roles: RoleCode[] = user?.roles?.map((r) => r.role_code as RoleCode) || [];
  const uniqueRoles = [...new Set(roles)];
  const currentRole = (activeRole || uniqueRoles[0] || 'MANAGEMENT') as RoleCode;

  // Filter nav sections based on user roles
  const allowedNavPaths = getNavSectionsForRole(user?.roles || []);
  const filteredNavSections = navSections
    .map(section => ({
      ...section,
      items: section.items.filter(item => {
        // Extract path without leading slash for comparison
        const navPath = item.path.substring(1);
        return allowedNavPaths.includes(navPath);
      }),
    }))
    .filter(section => section.items.length > 0); // Remove empty sections

  const handleRoleSwitch = (role: RoleCode) => {
    dispatch(setActiveRole(role));
  };

  const handleLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  // Dashboard status chips (top bar) from screenshot
  const topChips = [
    { label: '20 Breached', icon: '✕', color: '#922b21' as const, bg: '#fdecea' },
    { label: '7 Pending', icon: '⏳', color: '#b7950b' as const, bg: '#fef9e7' },
    { label: '1 SLA Met', icon: '✓', color: '#1e8449' as const, bg: '#e8f8f0' },
  ];

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* ─── Sidebar ─────────────────────────────────────── */}
      <Drawer
        variant={isMobile ? 'temporary' : 'persistent'}
        open={open}
        onClose={() => setOpen(false)}
        sx={{
          width: open ? DRAWER_WIDTH : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box', pt: 1 },
        }}
      >
        <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{
            width: 32, height: 32, borderRadius: 1, bgcolor: '#003366', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 12,
          }}>
            BIC
          </Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'primary.main', fontSize: '0.85rem' }}>
            B&I Data Metrics
          </Typography>
        </Box>
        <Divider sx={{ my: 1 }} />
        {filteredNavSections.map((section) => (
          <Box key={section.label} sx={{ mb: 1 }}>
            <Typography sx={{ px: 2, py: 0.5, fontSize: '0.65rem', fontWeight: 700, color: 'text.secondary', letterSpacing: 1 }}>
              {section.label}
            </Typography>
            <List dense disablePadding>
              {section.items.map((item) => (
                <ListItemButton
                  key={item.path}
                  selected={location.pathname.startsWith(item.path)}
                  onClick={() => navigate(item.path)}
                  sx={{
                    mx: 1, borderRadius: 1, mb: 0.3,
                    '&.Mui-selected': { bgcolor: 'primary.main', color: '#fff', '& .MuiListItemIcon-root': { color: '#fff' } },
                    '&.Mui-selected:hover': { bgcolor: 'primary.dark' },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 32, color: 'inherit' }}>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: '0.82rem', fontWeight: 500 }} />
                </ListItemButton>
              ))}
            </List>
          </Box>
        ))}
        {/* Logged-in user at bottom */}
        <Box sx={{ mt: 'auto', p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>Logged in as</Typography>
          <Typography sx={{ fontSize: '0.85rem', fontWeight: 700 }}>{user?.full_name}</Typography>
          <Chip
            label={roleLabel[currentRole]}
            size="small"
            sx={{ mt: 0.5, bgcolor: 'primary.main', color: '#fff', fontWeight: 600, fontSize: '0.7rem' }}
          />
        </Box>
      </Drawer>

      {/* ─── Main content ─────────────────────────────────── */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* ─── Top Bar ───────────────────────────────────── */}
        <AppBar position="sticky" elevation={0} sx={{ bgcolor: '#003366' }}>
          <Toolbar sx={{ minHeight: '48px !important', gap: 1 }}>
            <IconButton color="inherit" onClick={() => setOpen(!open)} edge="start" size="small">
              {open ? <ChevronLeft /> : <MenuIcon />}
            </IconButton>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mr: 2, whiteSpace: 'nowrap' }}>
              B&I Data Metrics and Controls
            </Typography>

            {/* ─── Role Switcher Tabs ─────────────────────── */}
            <Box sx={{ display: 'flex', gap: 0.5, flexGrow: 1 }}>
              {uniqueRoles.map((role) => (
                <Chip
                  key={role}
                  label={roleLabel[role]}
                  variant={role === currentRole ? 'filled' : 'outlined'}
                  onClick={() => handleRoleSwitch(role)}
                  size="small"
                  sx={{
                    color: role === currentRole ? '#003366' : '#ffffff',
                    bgcolor: role === currentRole ? '#ffffff' : 'transparent',
                    borderColor: '#ffffff50',
                    fontWeight: 600,
                    fontSize: '0.72rem',
                    '&:hover': { bgcolor: role === currentRole ? '#ffffff' : '#ffffff20' },
                  }}
                />
              ))}
            </Box>

            {/* ─── Status Chips ───────────────────────────── */}
            <Box sx={{ display: { xs: 'none', lg: 'flex' }, gap: 0.5 }}>
              {topChips.map((c) => (
                <Chip
                  key={c.label}
                  label={`${c.icon} ${c.label}`}
                  size="small"
                  sx={{ bgcolor: c.bg, color: c.color, fontWeight: 700, fontSize: '0.7rem', border: `1px solid ${c.color}30` }}
                />
              ))}
            </Box>

            {/* ─── Notifications & Avatar ─────────────────── */}
            <Tooltip title="Notifications">
              <IconButton color="inherit" size="small">
                <Badge badgeContent={3} color="error" variant="dot">
                  <Notifications fontSize="small" />
                </Badge>
              </IconButton>
            </Tooltip>
            <Tooltip title={user?.full_name || ''}>
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} size="small">
                <Avatar sx={{ width: 30, height: 30, bgcolor: '#c0392b', fontSize: 13, fontWeight: 700 }}>
                  {user?.full_name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
                </Avatar>
              </IconButton>
            </Tooltip>
            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
              <MenuItem disabled>
                <Typography variant="body2">{user?.soe_id} — {user?.email}</Typography>
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}><Logout fontSize="small" sx={{ mr: 1 }} /> Sign Out</MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>

        {/* ─── Page Content ───────────────────────────────── */}
        <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 }, overflow: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
