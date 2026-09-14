import { api } from "./api";

export interface GitHubConnection {
  id: string;
  github_login: string;
  github_user_id: number;
  avatar_url?: string;
  token_scope: string;
  created_at: string;
}

export interface RemoteRepo {
  github_repo_id: number;
  full_name: string;
  name: string;
  description?: string;
  default_branch: string;
  primary_language?: string;
  stars: number;
  is_private: boolean;
  html_url: string;
}

export interface TrackedRepo {
  id: string;
  github_repo_id: number;
  full_name: string;
  name: string;
  description?: string;
  default_branch: string;
  primary_language?: string;
  languages_json: Record<string, any>;
  stars: number;
  is_private: boolean;
  html_url: string;
  status: "idle" | "syncing" | "indexed" | "failed";
  files_indexed: number;
  error_message?: string;
  created_at: string;
}

export interface CodeFinding {
  id: string;
  pattern_id: string;
  category: "security" | "bug" | "performance" | "quality" | "style";
  severity: "critical" | "high" | "medium" | "low" | "info";
  file_path: string;
  line_start: number;
  line_end: number;
  description: string;
  suggestion: string;
  code_evidence: string;
  llm_explanation?: string;
  created_at: string;
}

export interface CodeAnalysisReport {
  id: string;
  repository_id: string;
  llm_review_included: boolean;
  total_files_analysed: number;
  total_findings: number;
  summary_json: {
    by_severity: Record<string, number>;
    by_category: Record<string, number>;
    top_files: Array<{ file_path: string; count: number }>;
  };
  created_at: string;
}

export interface CodebaseQAResponse {
  answer: string;
  citations: Array<{ source: string; snippet: string; score?: number }>;
}

export const githubService = {
  async getConnection(): Promise<GitHubConnection | null> {
    try {
      const resp = await api.get<GitHubConnection>("/github/connection");
      return resp.data;
    } catch {
      return null;
    }
  },

  async connectPAT(token: string): Promise<GitHubConnection> {
    const resp = await api.post<GitHubConnection>("/github/connect/pat", { personal_access_token: token });
    return resp.data;
  },

  async connectOAuth(code: string): Promise<GitHubConnection> {
    const resp = await api.post<GitHubConnection>("/github/connect/oauth", { code });
    return resp.data;
  },

  async disconnect(): Promise<void> {
    await api.delete("/github/connection");
  },

  async getRemoteRepos(): Promise<RemoteRepo[]> {
    const resp = await api.get<RemoteRepo[]>("/github/repos/remote");
    return resp.data;
  },

  async selectRepo(githubRepoId: number): Promise<TrackedRepo> {
    const resp = await api.post<TrackedRepo>(`/github/repos/select?github_repo_id=${githubRepoId}`);
    return resp.data;
  },

  async getTrackedRepos(): Promise<TrackedRepo[]> {
    const resp = await api.get<TrackedRepo[]>("/github/repos");
    return resp.data;
  },

  async getTrackedRepo(repoId: string): Promise<TrackedRepo> {
    const resp = await api.get<TrackedRepo>(`/github/repos/${repoId}`);
    return resp.data;
  },

  async triggerAnalysis(repoId: string, includeLlm: boolean = false): Promise<void> {
    await api.post(`/github/repos/${repoId}/analyze`, { include_llm_review: includeLlm });
  },

  async getLatestReport(repoId: string): Promise<CodeAnalysisReport> {
    const resp = await api.get<CodeAnalysisReport>(`/github/repos/${repoId}/reports/latest`);
    return resp.data;
  },

  async getFindings(repoId: string, category?: string, severity?: string): Promise<CodeFinding[]> {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (severity) params.append("severity", severity);
    const resp = await api.get<CodeFinding[]>(`/github/repos/${repoId}/findings?${params.toString()}`);
    return resp.data;
  },

  async queryCodebase(query: string, repositoryId?: string): Promise<CodebaseQAResponse> {
    const resp = await api.post<CodebaseQAResponse>("/github/qa", {
      query,
      repository_id: repositoryId,
    });
    return resp.data;
  },
};
