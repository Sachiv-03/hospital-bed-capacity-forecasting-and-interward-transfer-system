import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/api';
import { AuthTokens, User, UserRole } from '../types';

interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (full_name: string, email: string, password: string, role: UserRole, hospital_id?: number) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });

  const [tokens, setTokens] = useState<AuthTokens | null>(() => {
    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    if (accessToken && refreshToken) {
      return {
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: 'bearer',
        expires_in: 1800,
      };
    }
    return null;
  });

  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Fetch current user profile from /auth/me
  const refreshUser = useCallback(async () => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await apiClient.get<User>('/auth/me');
      setUser(response.data);
      localStorage.setItem('user', JSON.stringify(response.data));
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
      setUser(null);
      setTokens(null);
      localStorage.removeItem('user');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await apiClient.post<AuthTokens>('/auth/login', {
        email,
        password,
      });

      const tokenData = response.data;
      setTokens(tokenData);
      localStorage.setItem('access_token', tokenData.access_token);
      localStorage.setItem('refresh_token', tokenData.refresh_token);

      // Fetch profile for authenticated user
      const userResponse = await apiClient.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${tokenData.access_token}` },
      });

      setUser(userResponse.data);
      localStorage.setItem('user', JSON.stringify(userResponse.data));
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (full_name: string, email: string, password: string, role: UserRole, hospital_id?: number) => {
    setIsLoading(true);
    try {
      await apiClient.post('/auth/register', {
        full_name,
        email,
        password,
        role,
        hospital_id,
      });
      // Automatically log user in after successful registration
      await login(email, password);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    setTokens(null);
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    apiClient.post('/auth/logout').catch(() => {});
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tokens,
        isAuthenticated: !!user && !!tokens,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
