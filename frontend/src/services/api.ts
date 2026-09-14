import axios from "axios";

// Relative base URL: in dev, Vite's proxy (vite.config.ts) forwards this to
// FastAPI on :8000. In production, the frontend and backend are typically
// served behind the same reverse proxy, so a relative path still works.
export const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export const TOKEN_STORAGE_KEY = "careerforge_access_token";

// Attach the stored JWT (if any) to every outgoing request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 means the token is missing/invalid/expired — clear it so the app
// falls back to logged-out state. We don't redirect here: AuthContext/
// ProtectedRoute react to the auth state instead, so a stray 401 from a
// background request doesn't yank the user off whatever page they're on.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    return Promise.reject(error);
  }
);

/** Pulls a friendly message out of the backend's { success, error } shape. */
export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.error?.message;
    if (typeof message === "string") return message;
    if (error.code === "ERR_NETWORK") return "Can't reach the server. Is the backend running?";
  }
  return "Something went wrong. Please try again.";
}
