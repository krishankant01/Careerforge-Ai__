export interface User {
  id: string;
  name: string;
  email: string;
  github_username: string | null;
  target_role: string | null;
  target_location: string | null;
  experience_level: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}
