// Memory-only access token: survives SPA navigation, cleared on reload.
// The refresh token lives in an HttpOnly cookie set by the backend and is
// never accessible to JavaScript.
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
