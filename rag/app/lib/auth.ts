const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

// ── Token Storage ──────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

// ── Types ───────────────────────────────────────────────────────

export type User = {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  created_at: string;
};

// ── Auth API Calls ──────────────────────────────────────────────

export async function registerUser(
  email: string,
  fullName: string,
  password: string
): Promise<{ access_token: string; refresh_token: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: fullName, password }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(err.detail || "Registration failed");
  }

  return res.json();
}

export async function loginUser(
  email: string,
  password: string
): Promise<{ access_token: string; refresh_token: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail || "Invalid email or password");
  }

  return res.json();
}

export async function refreshTokens(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      clearTokens();
      return false;
    }

    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export async function getCurrentUser(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    let res = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    // If 401, try refreshing the token
    if (res.status === 401) {
      const refreshed = await refreshTokens();
      if (!refreshed) return null;

      const newToken = getAccessToken();
      res = await fetch(`${API_BASE_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${newToken}` },
      });
    }

    if (!res.ok) {
      clearTokens();
      return null;
    }

    return res.json();
  } catch {
    return null;
  }
}

export async function logoutUser(): Promise<void> {
  const token = getAccessToken();
  const refreshToken = getRefreshToken();

  if (token && refreshToken) {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Ignore logout API errors — we clear tokens locally either way
    }
  }

  clearTokens();
}

// ── Unified Authenticated Fetch Wrapper ──────────────────────────
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let token = getAccessToken();
  if (!token) {
    throw new Error("No access token found");
  }

  const headers = {
    ...options.headers,
    Authorization: `Bearer ${token}`,
  };

  let res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      token = getAccessToken();
      const retryHeaders = {
        ...options.headers,
        Authorization: `Bearer ${token}`,
      };
      res = await fetch(url, { ...options, headers: retryHeaders });
    } else {
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Session expired");
    }
  }

  return res;
}
