import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI, startAuthTimer, stopAuthTimer } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('vf_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('vf_access_token') || null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    stopAuthTimer();
    localStorage.removeItem('vf_access_token');
    localStorage.removeItem('vf_refresh_token');
    localStorage.removeItem('vf_user');
    setUser(null);
    setToken(null);
  }, []);

  // Listen for global logout event from Axios interceptor
  useEffect(() => {
    const handleGlobalLogout = () => {
      logout();
    };
    window.addEventListener('vf-auth-logout', handleGlobalLogout);
    return () => window.removeEventListener('vf-auth-logout', handleGlobalLogout);
  }, [logout]);

  // Bootstrap user session on initial load
  useEffect(() => {
    const bootstrapUser = async () => {
      const storedToken = localStorage.getItem('vf_access_token');
      if (storedToken) {
        try {
          // The axios interceptor will auto-refresh expired tokens
          const me = await authAPI.getMe();
          setUser(me);
          localStorage.setItem('vf_user', JSON.stringify(me));
          startAuthTimer();
        } catch (err) {
          // Only logout if interceptor failed to refresh (refresh token also expired)
          const refreshToken = localStorage.getItem('vf_refresh_token');
          if (!refreshToken || err.response?.status === 401) {
            console.warn('Session restoration failed:', err);
            logout();
          }
        }
      }
      setLoading(false);
    };

    bootstrapUser();
  }, [logout]);

  const login = async (email, password) => {
    const data = await authAPI.login(email, password);
    localStorage.setItem('vf_access_token', data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('vf_refresh_token', data.refresh_token);
    }
    setToken(data.access_token);
    startAuthTimer();

    const me = await authAPI.getMe();
    setUser(me);
    localStorage.setItem('vf_user', JSON.stringify(me));
    return me;
  };

  const register = async (email, password, fullName, role = 'operator') => {
    const userRes = await authAPI.register(email, password, fullName, role);
    // Automatically log in after registration
    return await login(email, password);
  };

  const value = {
    user,
    token,
    role: user?.role || 'operator',
    isAdmin: user?.role === 'admin',
    isOperator: user?.role === 'operator',
    isAuthenticated: !!user && !!token,
    loading,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
