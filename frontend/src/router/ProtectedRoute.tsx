import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";

import { useSession } from "@/features/auth/hooks/useSession";
import { getAccessToken } from "@/lib/tokenStore";

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const token = getAccessToken();
  const { isLoading } = useSession(); // runs only when no memory token

  if (!token && isLoading) {
    // Silent cookie refresh in flight (~1 round trip)
    return null;
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
