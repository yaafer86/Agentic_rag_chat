import { create } from "zustand";
import { clearTokens, getAccessToken, login as apiLogin, me, register as apiRegister } from "@/lib/api";

type User = {
  id: string;
  email: string;
  display_name: string;
  is_global_admin: boolean;
};

type AuthState = {
  user: User | null;
  loading: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  error: null,
  hydrate: async () => {
    if (!getAccessToken()) {
      set({ loading: false });
      return;
    }
    try {
      const user = await me();
      set({ user, loading: false });
    } catch {
      clearTokens();
      set({ user: null, loading: false });
    }
  },
  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      await apiLogin(email, password);
      const user = await me();
      set({ user, loading: false });
    } catch (e: any) {
      set({ error: e?.response?.data?.detail ?? "login failed", loading: false });
      throw e;
    }
  },
  register: async (email, password, displayName) => {
    set({ loading: true, error: null });
    try {
      await apiRegister(email, password, displayName);
      const user = await me();
      set({ user, loading: false });
    } catch (e: any) {
      set({ error: e?.response?.data?.detail ?? "registration failed", loading: false });
      throw e;
    }
  },
  logout: () => {
    clearTokens();
    set({ user: null });
  },
}));
