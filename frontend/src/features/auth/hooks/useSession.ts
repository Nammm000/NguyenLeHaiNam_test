import { useQuery } from "@tanstack/react-query";

import { getAccessToken } from "@/lib/tokenStore";
import { refreshSession } from "../api/auth";

/**
 * Boot-time silent refresh. With a memory-only access token every reload
 * starts unauthenticated; this query redeems the HttpOnly refresh cookie
 * before the app decides the user is logged out. `enabled: !getAccessToken()`
 * keeps it dormant once a token exists (e.g. right after login), so a boot
 * error state can never override a live session.
 */
export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: refreshSession,
    enabled: !getAccessToken(),
    staleTime: Infinity,
    retry: false,
  });
}
