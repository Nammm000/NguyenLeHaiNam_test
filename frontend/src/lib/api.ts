import axios, { type AxiosError } from "axios";

import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/tokenStore";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // send/receive the HttpOnly refresh cookie
});

// Requests whose 401s must never trigger refresh/redirect: auth failures
// handle their own errors, and exempting /auth/refresh prevents recursion.
// /auth/logout is deliberately NOT here: an expired access token on logout
// must refresh-and-retry so the backend clears the refresh cookie.
const REFRESH_EXEMPT_URLS = ["/auth/login", "/auth/register", "/auth/refresh"];

// Single-flight refresh: concurrent 401s share one /auth/refresh call
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = api
      .post<{ access_token: string }>("/auth/refresh")
      .then((response) => {
        setAccessToken(response.data.access_token);
        return response.data.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// Request interceptor: attach Bearer token from memory
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: on an expired access token, refresh once and retry
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as
      | (typeof error.config & { _retry?: boolean })
      | undefined;
    const isExempt = original?.url
      ? REFRESH_EXEMPT_URLS.some(
          (exempt) => original.url === exempt || original.url?.startsWith(`${exempt}?`)
        )
      : false;

    if (error.response?.status === 401 && original && !isExempt && !original._retry) {
      original._retry = true;
      const token = await refreshAccessToken();
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original); // retry exactly once
      }
      clearAccessToken();
      window.location.href = "/login"; // full reload also wipes the memory token
    }
    return Promise.reject(error);
  }
);
