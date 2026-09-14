import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  githubService,
  TrackedRepo,
  CodeAnalysisReport,
  CodeFinding,
  CodebaseQAResponse,
} from "../services/githubService";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import toast from "react-hot-toast";
import { Skeleton } from "../components/ui/skeleton";
import { Github, RefreshCw, Shield, CheckCircle, Search, Bot, Loader2 } from "lucide-react";

export default function CodeReviewDashboard() {
  const navigate = useNavigate();
  const [repos, setRepos] = useState<TrackedRepo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<TrackedRepo | null>(null);
  const [report, setReport] = useState<CodeAnalysisReport | null>(null);
  const [findings, setFindings] = useState<CodeFinding[]>([]);

  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [includeLlm, setIncludeLlm] = useState(false);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("");

  // Codebase RAG Chat
  const [qaQuery, setQaQuery] = useState("");
  const [qaResult, setQaResult] = useState<CodebaseQAResponse | null>(null);
  const [askingQa, setAskingQa] = useState(false);

  useEffect(() => {
    loadRepos();
  }, []);

  useEffect(() => {
    if (selectedRepo) {
      loadReportAndFindings(selectedRepo.id);
    }
  }, [selectedRepo, selectedCategory, selectedSeverity]);

  async function loadRepos() {
    setLoading(true);
    try {
      const data = await githubService.getTrackedRepos();
      setRepos(data);
      if (data.length > 0 && !selectedRepo) {
        setSelectedRepo(data[0]);
      }
    } catch {
      toast.error("Failed to load repositories");
    } finally {
      setLoading(false);
    }
  }

  async function loadReportAndFindings(repoId: string) {
    try {
      const rep = await githubService.getLatestReport(repoId);
      setReport(rep);
      const find = await githubService.getFindings(repoId, selectedCategory || undefined, selectedSeverity || undefined);
      setFindings(find);
    } catch {
      setReport(null);
      setFindings([]);
    }
  }

  async function handleTriggerAnalysis() {
    if (!selectedRepo) return;
    setAnalyzing(true);
    const toastId = toast.loading("Starting code analysis...");
    try {
      await githubService.triggerAnalysis(selectedRepo.id, includeLlm);
      setSelectedRepo({ ...selectedRepo, status: "syncing" });
      toast.success("Analysis started successfully", { id: toastId });
      setTimeout(() => {
        loadRepos();
        if (selectedRepo) loadReportAndFindings(selectedRepo.id);
      }, 3000);
    } catch {
      toast.error("Failed to start analysis", { id: toastId });
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleAskQa(e: React.FormEvent) {
    e.preventDefault();
    if (!qaQuery.trim()) return;
    setAskingQa(true);
    const toastId = toast.loading("Querying codebase...");
    try {
      const res = await githubService.queryCodebase(qaQuery, selectedRepo?.id);
      setQaResult(res);
      toast.success("Answer found", { id: toastId });
    } catch {
      toast.error("Codebase query failed", { id: toastId });
    } finally {
      setAskingQa(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Code Intelligence</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Static code audit, severity breakdown, and AI-powered codebase search.
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate("/github/connect")} size="sm">
          <Github className="w-4 h-4 mr-2" />
          Manage Repositories
        </Button>
      </div>

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : repos.length === 0 ? (
        <Card className="border-dashed bg-muted/10 shadow-none">
          <CardContent className="flex flex-col items-center justify-center py-20 text-center">
            <div className="p-5 bg-primary/10 text-primary rounded-full mb-6">
              <Github className="w-10 h-10" />
            </div>
            <h3 className="text-xl font-semibold mb-2 text-foreground">No repositories connected</h3>
            <p className="text-muted-foreground max-w-md mx-auto mb-6 text-sm">
              Connect your GitHub account to analyze your projects and get AI-powered code reviews.
            </p>
            <Button onClick={() => navigate("/github/connect")}>
              Connect GitHub
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* REPO SELECTOR TABS */}
          <div className="flex gap-1 border-b overflow-x-auto scrollbar-hide">
            {repos.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelectedRepo(r)}
                className={`px-4 py-2.5 font-medium text-sm transition-colors flex items-center gap-2 whitespace-nowrap border-b-2 ${
                  selectedRepo?.id === r.id
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                <span>{r.name}</span>
                <span
                  className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-widest border ${
                    r.status === "indexed"
                      ? "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800"
                      : r.status === "syncing"
                      ? "bg-amber-100 text-amber-700 border-amber-200 animate-pulse dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800"
                      : "bg-muted text-muted-foreground border-border"
                  }`}
                >
                  {r.status}
                </span>
              </button>
            ))}
          </div>

          {selectedRepo && (
            <div className="space-y-6 animate-fade-in-up">
              {/* ACTION BAR */}
              <Card className="shadow-sm">
                <CardContent className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-bold flex items-center gap-2 text-foreground">
                      <Github className="w-5 h-5 text-muted-foreground" />
                      {selectedRepo.full_name}
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1.5 flex items-center gap-2">
                      <span className="flex items-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                        {selectedRepo.files_indexed} files indexed
                      </span>
                      <span className="text-muted-foreground/30">•</span>
                      <span className="font-mono bg-muted px-1.5 py-0.5 rounded border">
                        {selectedRepo.default_branch}
                      </span>
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-4">
                    <label className="flex items-center gap-2 text-sm font-medium cursor-pointer text-foreground hover:text-primary transition-colors">
                      <input
                        type="checkbox"
                        checked={includeLlm}
                        onChange={(e) => setIncludeLlm(e.target.checked)}
                        className="rounded border-input text-primary focus:ring-primary h-4 w-4"
                      />
                      Deep AI Review
                    </label>

                    <Button
                      onClick={handleTriggerAnalysis}
                      disabled={analyzing || selectedRepo.status === "syncing"}
                      className="gap-2"
                      size="sm"
                    >
                      {analyzing || selectedRepo.status === "syncing" ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4" />
                      )}
                      Run Analysis
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* METRICS */}
              {report && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <MetricCard title="Critical" count={report.summary_json.by_severity?.critical || 0} colorClass="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400" />
                  <MetricCard title="High" count={report.summary_json.by_severity?.high || 0} colorClass="border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-900/20 dark:text-orange-400" />
                  <MetricCard title="Medium" count={report.summary_json.by_severity?.medium || 0} colorClass="border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-400" />
                  <MetricCard title="Low" count={report.summary_json.by_severity?.low || 0} colorClass="border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-400" />
                  <MetricCard title="Info" count={report.summary_json.by_severity?.info || 0} colorClass="border-border bg-muted/50 text-muted-foreground" />
                </div>
              )}

              {/* RAG QA */}
              <Card className="bg-primary/5 border-primary/20 shadow-sm relative overflow-hidden">
                <CardContent className="p-6 md:p-8 relative z-10">
                  <div className="flex items-center gap-2 mb-2">
                    <Bot className="w-5 h-5 text-primary" />
                    <h3 className="text-lg font-semibold text-foreground">Codebase AI Assistant</h3>
                  </div>
                  <p className="text-muted-foreground mb-5 text-sm">
                    Ask architectural or implementation questions about <span className="text-foreground font-medium">{selectedRepo.name}</span>.
                  </p>

                  <form onSubmit={handleAskQa} className="flex gap-3">
                    <Input
                      placeholder="e.g. How does the authentication work?"
                      value={qaQuery}
                      onChange={(e) => setQaQuery(e.target.value)}
                      className="flex-1 bg-background"
                    />
                    <Button
                      type="submit"
                      disabled={askingQa || !qaQuery.trim()}
                    >
                      {askingQa ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Search className="w-4 h-4 mr-2" />}
                      Ask AI
                    </Button>
                  </form>

                  {qaResult && (
                    <div className="mt-5 p-5 bg-background rounded-md border text-sm space-y-4 animate-fade-in-up">
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap">{qaResult.answer}</p>
                      {qaResult.citations.length > 0 && (
                        <div className="pt-3 border-t">
                          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider flex items-center gap-2">
                            Citations
                          </p>
                          <div className="space-y-1.5">
                            {qaResult.citations.map((c, i) => (
                              <div key={i} className="text-xs text-muted-foreground font-mono flex items-start gap-2 bg-muted/50 p-2 rounded border">
                                <span className="text-primary mt-0.5">❯</span>
                                <span className="break-all">{c.source}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* FINDINGS TABLE */}
              <Card className="shadow-sm">
                <CardHeader className="flex flex-col md:flex-row md:items-end justify-between border-b pb-4 gap-4">
                  <div>
                    <CardTitle className="text-lg">Code Findings</CardTitle>
                    <CardDescription className="text-sm mt-1">Potential issues and improvements ({findings.length})</CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value)}
                      className="h-9 px-3 border rounded-md text-sm bg-background text-foreground focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                    >
                      <option value="">All Categories</option>
                      <option value="security">Security</option>
                      <option value="bug">Bug</option>
                      <option value="performance">Performance</option>
                      <option value="quality">Quality</option>
                      <option value="style">Style</option>
                    </select>

                    <select
                      value={selectedSeverity}
                      onChange={(e) => setSelectedSeverity(e.target.value)}
                      className="h-9 px-3 border rounded-md text-sm bg-background text-foreground focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                    >
                      <option value="">All Severities</option>
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                      <option value="info">Info</option>
                    </select>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  {findings.length === 0 ? (
                    <div className="py-16 text-center text-muted-foreground flex flex-col items-center">
                      <Shield className="w-10 h-10 mb-3 text-muted-foreground opacity-30" />
                      <p className="text-sm font-medium">No potential issues detected matching your filters.</p>
                    </div>
                  ) : (
                    <div className="divide-y">
                      {findings.map((f) => (
                        <div key={f.id} className="p-5 md:p-6 space-y-3 hover:bg-muted/10 transition-colors">
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <SeverityBadge severity={f.severity} />
                              <span className="text-[10px] font-bold tracking-wider uppercase bg-secondary border px-2 py-0.5 rounded text-secondary-foreground">
                                {f.category}
                              </span>
                              <span className="text-xs text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded border">{f.pattern_id}</span>
                            </div>
                            <span className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded border border-primary/20">
                              {f.file_path}:{f.line_start}-{f.line_end}
                            </span>
                          </div>

                          <p className="text-sm font-medium text-foreground">{f.description}</p>
                          
                          {f.suggestion && (
                            <div className="text-sm text-primary-800 bg-primary/5 p-3 rounded-md border border-primary/10 flex items-start gap-2">
                              <span className="text-base leading-none">💡</span>
                              <div>
                                <strong className="block mb-0.5 text-foreground text-xs uppercase tracking-wider">Recommendation</strong>
                                <span className="text-muted-foreground">{f.suggestion}</span>
                              </div>
                            </div>
                          )}

                          {f.code_evidence && (
                            <div className="mt-3">
                              <pre className="p-3 bg-muted/50 text-muted-foreground text-xs font-mono rounded-md overflow-x-auto border">
                                <code>{f.code_evidence}</code>
                              </pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MetricCard({ title, count, colorClass }: { title: string; count: number; colorClass: string }) {
  return (
    <Card className={`overflow-hidden border shadow-sm transition-transform hover:-translate-y-0.5 ${colorClass}`}>
      <CardContent className="p-4 text-center">
        <p className="text-3xl font-bold mb-1">{count}</p>
        <p className="text-[10px] font-semibold uppercase tracking-wider opacity-80">{title}</p>
      </CardContent>
    </Card>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critical: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800",
    high: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:border-orange-800",
    medium: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
    low: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800",
    info: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
  };
  return (
    <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider border ${styles[severity] || "bg-muted text-muted-foreground border-border"}`}>
      {severity}
    </span>
  );
}
