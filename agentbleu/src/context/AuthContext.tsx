import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import {
  login,
  register,
  authStatus,
  setAuthToken,
  getAuthToken,
  type LoginRequest,
  type RegisterRequest,
  type TokenResponse,
} from '../api';

interface AuthContextType {
  user: { user_id: string; email?: string } | null;
  token: string | null;
  loading: boolean;
  authenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<{ user_id: string; email?: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      authStatus()
        .then(() => {
          setUser({ user_id: token });
          setLoading(false);
        })
        .catch(() => {
          setAuthToken(null);
          localStorage.removeItem('agentbleu_token');
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = async (data: LoginRequest) => {
    const res: TokenResponse = await login(data);
    setAuthToken(res.access_token);
    localStorage.setItem('agentbleu_token', res.access_token);
    setUser({ user_id: res.user_id });
  };

  const handleRegister = async (data: RegisterRequest) => {
    const res: TokenResponse = await register(data);
    setAuthToken(res.access_token);
    localStorage.setItem('agentbleu_token', res.access_token);
    setUser({ user_id: res.user_id });
  };

  const handleLogout = () => {
    setAuthToken(null);
    localStorage.removeItem('agentbleu_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token: getAuthToken(),
        loading,
        authenticated: !!getAuthToken(),
        login: handleLogin,
        register: handleRegister,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
