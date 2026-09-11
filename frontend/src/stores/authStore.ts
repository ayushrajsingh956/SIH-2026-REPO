import { create } from "zustand";

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: "admin" | "inspector" | "viewer";
  district?: string | null;
  state?: string | null;
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (tokens: { accessToken: string; refreshToken: string }, user: UserProfile) => void;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  initialize: () => void;
}

const STORAGE_KEY_USER = "legalmetro_user";
const STORAGE_KEY_ACCESS = "legalmetro_access_token";
const STORAGE_KEY_REFRESH = "legalmetro_refresh_token";

const STORAGE_KEYS = [STORAGE_KEY_USER, STORAGE_KEY_ACCESS, STORAGE_KEY_REFRESH] as const;

const clearPersistedAuth = () => {
  STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,

  initialize: () => {
    try {
      const storedUser = localStorage.getItem(STORAGE_KEY_USER);
      const storedAccess = localStorage.getItem(STORAGE_KEY_ACCESS);
      const storedRefresh = localStorage.getItem(STORAGE_KEY_REFRESH);

      if (storedUser && storedAccess) {
        set({
          user: JSON.parse(storedUser),
          accessToken: storedAccess,
          refreshToken: storedRefresh,
          isAuthenticated: true,
        });
      }
    } catch {
      clearPersistedAuth();
    }
  },

  login: (tokens, user) => {
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
    localStorage.setItem(STORAGE_KEY_ACCESS, tokens.accessToken);
    localStorage.setItem(STORAGE_KEY_REFRESH, tokens.refreshToken);
    set({
      user,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      isAuthenticated: true,
    });
  },

  logout: () => {
    clearPersistedAuth();
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    });
  },

  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem(STORAGE_KEY_ACCESS, accessToken);
    localStorage.setItem(STORAGE_KEY_REFRESH, refreshToken);
    set({ accessToken, refreshToken });
  },
}));
