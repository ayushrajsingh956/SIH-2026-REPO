import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/authStore";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  headers: {
    "Content-Type": "application/json",
  },
});

// Request Interceptor: inject Bearer token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().accessToken;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: refresh flow stub
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = useAuthStore.getState().refreshToken;

      if (refreshToken) {
        try {
          // In Phase 1: POST /api/v1/auth/refresh
          // const res = await axios.post("/api/v1/auth/refresh", { refresh_token: refreshToken });
          // const newAccessToken = res.data.access_token;
          // useAuthStore.getState().setAccessToken(newAccessToken);
          // originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          // return apiClient(originalRequest);
        } catch (refreshErr) {
          useAuthStore.getState().logout();
          return Promise.reject(refreshErr);
        }
      } else {
        useAuthStore.getState().logout();
      }
    }

    return Promise.reject(error);
  }
);
