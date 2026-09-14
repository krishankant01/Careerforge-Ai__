import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { extractErrorMessage } from "../services/api";
import { listMatchesForResume } from "../services/jobService";
import { getResume } from "../services/resumeService";
import type { JobMatchWithJob } from "../types/job";
import type { ResumeDetail } from "../types/resume";
import { Card, CardContent } from "../components/ui/card";
import { Loader2 } from "lucide-react";

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-900/30 dark:border-emerald-800";
  if (score >= 50) return "text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-900/30 dark:border-amber-800";
  return "text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-900/30 dark:border-red-800";
}

export default function JobComparisonDashboard() {
  const { resumeId } = useParams<{ resumeId: string }>();
  const [resume, setResume] = useState<ResumeDetail | null>(null);
  const [matches, setMatches] = useState<JobMatchWithJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!resumeId) return;
    (async () => {
      try {
        const [resumeData, matchData] = await Promise.all([
          getResume(resumeId),
          listMatchesForResume(resumeId),
        ]);
        setResume(resumeData);
        setMatches(matchData);
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    })();
  }, [resumeId]);

  return (
    <div className="min-h-screen bg-background relative pb-10">
      <div className="mx-auto max-w-5xl">
        <Link to={`/resumes/${resumeId}`} className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 w-fit mb-6">
          ← Back to resume
        </Link>
        
        <div className="mb-8 border-b pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Job Comparison</h1>
          {resume && <p className="mt-1 text-sm text-muted-foreground">Comparing against: <span className="text-foreground font-medium">{resume.original_filename}</span></p>}
        </div>

        {isLoading && (
          <div className="mt-12 flex flex-col items-center justify-center space-y-4">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground animate-pulse">Loading comparison data…</p>
          </div>
        )}
        
        {error && (
          <div role="alert" className="mt-6 rounded-md bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {!isLoading && matches.length === 0 && !error && (
          <Card className="mt-8 bg-muted/10 border-dashed shadow-none">
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4">
                <span className="text-2xl">🔍</span>
              </div>
              <p className="text-sm font-medium text-foreground mb-2">No jobs matched yet</p>
              <p className="text-xs text-muted-foreground max-w-md">
                Analyze a job description and run a match from the Job Analyzer page to see comparisons here.
              </p>
            </CardContent>
          </Card>
        )}

        {matches.length > 0 && (
          <div className="mt-6 overflow-hidden rounded-md border bg-card shadow-sm animate-fade-in-up">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/30 text-left text-xs uppercase tracking-widest text-muted-foreground">
                    <th className="px-6 py-4 font-semibold">Job</th>
                    <th className="px-6 py-4 font-semibold">Overall</th>
                    <th className="px-6 py-4 font-semibold">Required</th>
                    <th className="px-6 py-4 font-semibold">Preferred</th>
                    <th className="px-6 py-4 font-semibold">Mode</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {matches.map((match) => (
                    <tr key={match.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex flex-col">
                          <Link
                            to={`/jobs?highlight=${match.job_id}`}
                            className="font-medium text-foreground hover:text-primary transition-colors"
                          >
                            {match.job_title ?? "Untitled posting"}
                          </Link>
                          {match.job_company && (
                            <span className="text-xs text-muted-foreground mt-1">{match.job_company}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold border ${scoreColor(match.compatibility_score)}`}>
                          {match.compatibility_score}%
                        </span>
                      </td>
                      <td className="px-6 py-4 text-foreground font-medium">{match.required_coverage_score}%</td>
                      <td className="px-6 py-4 text-foreground font-medium">{match.preferred_coverage_score}%</td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2 py-1 rounded text-[10px] font-medium uppercase tracking-wider bg-secondary text-secondary-foreground border border-border">
                          {match.semantic_mode === "ai_assisted" ? "AI-assisted" : "Deterministic"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
