import { create } from "zustand";

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: "admin" | "inspector" | "viewer";
  district?: string;
  state?: string;
}

interface AuthState {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (tokens: { accessToken: string; refreshToken: string }, user: UserProfile) => void;
  logout: () => void;
  setAccessToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Inspector Sharma",
    email: "inspector.doca@nic.in",
    role: "inspector",
    district: "New Delhi",
    state: "Delhi",
  },
  accessToken: "stubbed-dev-access-token",
  refreshToken: "stubbed-dev-refresh-token",
  isAuthenticated: true, // Stubbed for initial scaffold; toggleable in UI
  login: (tokens, user) =>
    set({
      user,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      isAuthenticated: true,
    }),
  logout: () =>
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    }),
  setAccessToken: (token) => set({ accessToken: token }),
}));
