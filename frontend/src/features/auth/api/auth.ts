import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import { clearAccessToken, setAccessToken } from "@/lib/tokenStore";

interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  email: string;
  password: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function useLogin() {
  return useMutation({
    mutationFn: async (data: LoginRequest): Promise<TokenResponse> => {
      const response = await api.post("/auth/login", data);
      return response.data;
    },
    onSuccess: (data) => {
      // The refresh token arrives as an HttpOnly cookie handled by the browser
      setAccessToken(data.access_token);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (data: RegisterRequest): Promise<TokenResponse> => {
      const response = await api.post("/auth/register", data);
      return response.data;
    },
    onSuccess: (data) => {
      setAccessToken(data.access_token);
    },
  });
}

export function useLogout() {
  return useMutation({
    mutationFn: async () => {
      await api.post("/auth/logout");
    },
    onSuccess: () => {
      clearAccessToken();
      queryClient.clear();
    },
  });
}

export async function refreshSession(): Promise<TokenResponse> {
  const response = await api.post("/auth/refresh");
  const data: TokenResponse = response.data;
  setAccessToken(data.access_token);
  return data;
}

interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  const response = await api.get("/auth/me");
  return response.data;
}
