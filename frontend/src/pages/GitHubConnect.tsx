import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { githubService, GitHubConnection, RemoteRepo } from "../services/githubService";
import { Loader2, Github, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export default function GitHubConnect() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const oauthCode = searchParams.get("code");

  const [connection, setConnection] = useState<GitHubConnection | null>(null);
  const [patToken, setPatToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [remoteRepos, setRemoteRepos] = useState<RemoteRepo[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selecting, setSelecting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      if (oauthCode) {
        const conn = await githubService.connectOAuth(oauthCode);
        setConnection(conn);
        await fetchRepos();
      } else {
        const conn = await githubService.getConnection();
        setConnection(conn);
        if (conn) {
          await fetchRepos();
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load GitHub connection state.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchRepos() {
    setLoadingRepos(true);
    try {
      const repos = await githubService.getRemoteRepos();
      setRemoteRepos(repos);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to fetch repositories from GitHub.");
    } finally {
      setLoadingRepos(false);
    }
  }

  async function handleConnectPAT(e: React.FormEvent) {
    e.preventDefault();
    if (!patToken.trim()) return;
    setConnecting(true);
    setError(null);
    try {
      const conn = await githubService.connectPAT(patToken.trim());
      setConnection(conn);
      setPatToken("");
      await fetchRepos();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to connect using PAT.");
    } finally {
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    if (!confirm("Are you sure you want to disconnect your GitHub account?")) return;
    try {
      await githubService.disconnect();
      setConnection(null);
      setRemoteRepos([]);
    } catch (err: any) {
      setError("Failed to disconnect GitHub account.");
    }
  }

  function toggleRepoSelect(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  }

  async function handleTrackSelected() {
    if (selectedIds.length === 0) return;
    setSelecting(true);
    try {
      for (const id of selectedIds) {
        await githubService.selectRepo(id);
      }
      navigate("/github/dashboard");
    } catch (err: any) {
      setError("Failed to track selected repositories.");
    } finally {
      setSelecting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background relative pb-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <Link to="/dashboard" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors mb-2 inline-block">
              ← Back to Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">GitHub Integration</h1>
            <p className="text-muted-foreground mt-1 text-sm">Connect your account & select repositories for Code Intelligence.</p>
          </div>
          <Link 
            to="/github/dashboard"
            className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 py-2 px-4"
          >
            Code Dashboard →
          </Link>
        </div>

        {error && (
          <div className="p-4 bg-destructive/10 border border-destructive/20 text-destructive rounded-md text-sm animate-fade-in-up">
            {error}
          </div>
        )}

        {/* CONNECTION STATUS */}
        <Card className="shadow-sm">
          <CardHeader className="border-b">
            <CardTitle className="text-lg flex items-center gap-2">
              <Github className="w-5 h-5 text-muted-foreground" />
              Account Connection
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            {loading ? (
              <div className="flex items-center gap-3 text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin" />
                <p className="text-sm">Checking connection status...</p>
              </div>
            ) : connection ? (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 bg-muted/30 border rounded-md gap-6">
                <div className="flex items-center gap-4">
                  {connection.avatar_url ? (
                    <img src={connection.avatar_url} alt="Avatar" className="w-12 h-12 rounded-full border border-border" />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center font-semibold text-primary text-lg">
                      {connection.github_login.slice(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div>
                    <h3 className="font-semibold text-foreground flex items-center gap-2">
                      {connection.github_login}
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">Connected via <span className="font-medium">{connection.token_scope || "PAT"}</span></p>
                  </div>
                </div>
                <Button
                  onClick={handleDisconnect}
                  variant="destructive"
                  size="sm"
                >
                  Disconnect Account
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-5 bg-muted/10 border border-dashed rounded-md">
                  <h3 className="text-sm font-semibold text-foreground mb-3">Connect via Personal Access Token (PAT)</h3>
                  <form onSubmit={handleConnectPAT} className="flex flex-col sm:flex-row gap-3">
                    <Input
                      type="password"
                      placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                      value={patToken}
                      onChange={(e) => setPatToken(e.target.value)}
                      className="flex-1"
                    />
                    <Button
                      type="submit"
                      disabled={connecting || !patToken.trim()}
                    >
                      {connecting ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Connecting...
                        </span>
                      ) : "Connect PAT"}
                    </Button>
                  </form>
                  <p className="text-xs text-muted-foreground mt-3">
                    Token requires <code className="bg-muted px-1 py-0.5 rounded text-foreground font-mono">repo</code> and <code className="bg-muted px-1 py-0.5 rounded text-foreground font-mono">read:user</code> scopes.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* REPOSITORY SELECTION */}
        {connection && (
          <Card className="shadow-sm animate-fade-in-up" style={{ animationDelay: '100ms' }}>
            <CardHeader className="border-b flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-lg">Select Repositories to Analyze</CardTitle>
                <CardDescription className="mt-1">Choose which repositories you want to sync and audit.</CardDescription>
              </div>
              <Button
                onClick={handleTrackSelected}
                disabled={selectedIds.length === 0 || selecting}
              >
                {selecting ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving...
                  </span>
                ) : `Track Selected (${selectedIds.length})`}
              </Button>
            </CardHeader>
            <CardContent className="pt-6">
              {loadingRepos ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
                  <p className="text-sm">Fetching repositories from GitHub...</p>
                </div>
              ) : remoteRepos.length === 0 ? (
                <div className="text-center py-12 bg-muted/10 border border-dashed rounded-md">
                  <Github className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-50" />
                  <p className="text-sm font-medium text-foreground">No accessible repositories found.</p>
                  <p className="text-xs text-muted-foreground mt-1">Make sure your PAT has the correct scopes.</p>
                </div>
              ) : (
                <div className="divide-y divide-border max-h-[500px] overflow-y-auto pr-2 custom-scrollbar border rounded-md">
                  {remoteRepos.map((repo) => {
                    const isSelected = selectedIds.includes(repo.github_repo_id);
                    return (
                      <div
                        key={repo.github_repo_id}
                        onClick={() => toggleRepoSelect(repo.github_repo_id)}
                        className={`flex flex-col sm:flex-row sm:items-center justify-between p-4 cursor-pointer transition-colors ${
                          isSelected ? "bg-primary/5" : "hover:bg-muted/30"
                        }`}
                      >
                        <div className="flex items-start gap-4">
                          <div className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                            isSelected ? "bg-primary border-primary text-primary-foreground" : "border-input bg-background"
                          }`}>
                            {isSelected && <CheckCircle2 className="w-3 h-3" />}
                          </div>
                          <div>
                            <p className={`font-semibold text-sm transition-colors ${isSelected ? "text-primary" : "text-foreground"}`}>{repo.full_name}</p>
                            {repo.description && (
                              <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{repo.description}</p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-4 mt-3 sm:mt-0 ml-8 sm:ml-0 text-xs">
                          {repo.primary_language && (
                            <span className="px-2.5 py-0.5 bg-secondary text-secondary-foreground rounded-md font-medium border">
                              {repo.primary_language}
                            </span>
                          )}
                          <span className="flex items-center gap-1 text-muted-foreground font-medium">
                            ⭐ {repo.stars}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
