import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useLogout, fetchCurrentUser } from "../api/auth";
import { useSession } from "./useSession";
import { queryClient } from "@/lib/queryClient";
import { clearAccessToken, getAccessToken } from "@/lib/tokenStore";

export function useAuth() {
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  const { data: session, isLoading: sessionLoading } = useSession();
  const isAuthenticated = !!getAccessToken() || !!session;

  const {
    data: user,
    isLoading: currentUserLoading,
    error,
  } = useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
    enabled: isAuthenticated,
    retry: false,
  });

  const logout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        navigate("/login");
      },
      onError: () => {
        // Even on error, clear the session and redirect
        clearAccessToken();
        queryClient.clear();
        navigate("/login");
      },
    });
  };

  return {
    user,
    isAuthenticated,
    isLoading: sessionLoading || currentUserLoading,
    error,
    logout,
  };
}
