import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAppSelector } from '../../store';
import { RoleCode } from '../../types';

interface RequireRoleProps {
  roles: RoleCode[];
  children: React.ReactNode;
  fallbackPath?: string;
}

/**
 * ProtectedRoute wrapper that checks if user has required roles.
 * Silently redirects to dashboard (or fallback path) if unauthorized.
 * 
 * Usage:
 *   <RequireRole roles={["SYSTEM_ADMIN"]}>
 *     <AdminPage />
 *   </RequireRole>
 */
export function RequireRole({ roles, children, fallbackPath = '/dashboard' }: RequireRoleProps) {
  const { user } = useAppSelector((s) => s.auth);

  // If no user, redirect to dashboard (ProtectedRoute already checked auth)
  if (!user) {
    return <Navigate to={fallbackPath} replace />;
  }

  // Check if user has any of the required roles
  const userRoleCodes = new Set(user.roles.map((r) => r.role_code));
  const hasRequiredRole = roles.some((role) => userRoleCodes.has(role));

  // If user doesn't have required role, redirect to fallback path
  if (!hasRequiredRole) {
    return <Navigate to={fallbackPath} replace />;
  }

  // User has required role, render children
  return <>{children}</>;
}
