import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#003366', light: '#1a5276', dark: '#001a33' },
    secondary: { main: '#c0392b', light: '#e74c3c', dark: '#922b21' },
    success: { main: '#27ae60', light: '#2ecc71', dark: '#1e8449' },
    warning: { main: '#f39c12', light: '#f1c40f', dark: '#d68910' },
    error: { main: '#c0392b', light: '#e74c3c', dark: '#922b21' },
    background: { default: '#f0f2f5', paper: '#ffffff' },
    text: { primary: '#1a1a2e', secondary: '#546e7a' },
    divider: '#e0e4e8',
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "Segoe UI", Roboto, sans-serif',
    h4: { fontWeight: 700, fontSize: '1.5rem' },
    h5: { fontWeight: 600, fontSize: '1.25rem' },
    h6: { fontWeight: 600, fontSize: '1.1rem' },
    subtitle1: { fontWeight: 500 },
    body2: { fontSize: '0.875rem', color: '#546e7a' },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
          border: '1px solid #e0e4e8',
          '&:hover': { boxShadow: '0 4px 12px rgba(0,0,0,0.1)' },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, borderRadius: 6 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, fontSize: '0.75rem' },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 700, backgroundColor: '#f8f9fa', color: '#003366' },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { backgroundColor: '#003366', boxShadow: '0 2px 8px rgba(0,0,0,0.15)' },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: { backgroundColor: '#ffffff', borderRight: '1px solid #e0e4e8' },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, minHeight: 42 },
      },
    },
  },
});

export default theme;
