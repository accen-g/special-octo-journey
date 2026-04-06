import { configureStore, createSlice, PayloadAction } from '@reduxjs/toolkit';
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import type { CurrentUser, AuthState } from '../types';

// ─── Auth Slice ─────────────────────────────────────────────
const savedUser = localStorage.getItem('bic_user');
const savedToken = localStorage.getItem('bic_token');

const initialAuth: AuthState = {
  user: savedUser ? JSON.parse(savedUser) : null,
  token: savedToken || null,
  isAuthenticated: !!savedToken,
};

const authSlice = createSlice({
  name: 'auth',
  initialState: initialAuth,
  reducers: {
    loginSuccess: (state, action: PayloadAction<{ user: CurrentUser; token: string }>) => {
      state.user = action.payload.user;
      state.token = action.payload.token;
      state.isAuthenticated = true;
      localStorage.setItem('bic_user', JSON.stringify(action.payload.user));
      localStorage.setItem('bic_token', action.payload.token);
    },
    logout: (state) => {
      state.user = null;
      state.token = null;
      state.isAuthenticated = false;
      localStorage.removeItem('bic_user');
      localStorage.removeItem('bic_token');
    },
    updateUser: (state, action: PayloadAction<CurrentUser>) => {
      state.user = action.payload;
      localStorage.setItem('bic_user', JSON.stringify(action.payload));
    },
  },
});

export const { loginSuccess, logout, updateUser } = authSlice.actions;

// ─── UI Slice ───────────────────────────────────────────────
interface UIState {
  sidebarOpen: boolean;
  selectedPeriod: { year: number; month: number };
  selectedRegionId: number | null;
  activeRole: string | null;
}

const now = new Date();
const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    sidebarOpen: true,
    selectedPeriod: { year: now.getFullYear(), month: now.getMonth() + 1 },
    selectedRegionId: null,
    activeRole: null,
  } as UIState,
  reducers: {
    toggleSidebar: (state) => { state.sidebarOpen = !state.sidebarOpen; },
    setPeriod: (state, action: PayloadAction<{ year: number; month: number }>) => {
      state.selectedPeriod = action.payload;
    },
    setRegion: (state, action: PayloadAction<number | null>) => {
      state.selectedRegionId = action.payload;
    },
    setActiveRole: (state, action: PayloadAction<string | null>) => {
      state.activeRole = action.payload;
    },
  },
});

export const { toggleSidebar, setPeriod, setRegion, setActiveRole } = uiSlice.actions;

// ─── Store ──────────────────────────────────────────────────
export const store = configureStore({
  reducer: {
    auth: authSlice.reducer,
    ui: uiSlice.reducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
