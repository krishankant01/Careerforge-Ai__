import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ScoreBar } from "../components/ScoreBar";
import { StatusBadge } from "../components/StatusBadge";
import { extractErrorMessage } from "../services/api";
import { getResume, getResumeAnalysis } from "../services/resumeService";
import type { ResumeAnalysis, ResumeDetail } from "../types/resume";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export default function ResumeAnalysisPage() {
  const { resumeId } = useParams<{ resumeId: string }>();
  const [resume, setResume] = useState<ResumeDetail | null>(null);
  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!resumeId) return;
    (async () => {
      try {
        const resumeData = await getResume(resumeId);
        setResume(resumeData);
        if (resumeData.status === "completed") {
          const analysisData = await getResumeAnalysis(resumeId);
          setAnalysis(analysisData);
        }
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
        <div className="flex items-center justify-between mb-6">
          <Link to="/resumes" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
            ← All resumes
          </Link>
          {resumeId && (
            <Link to={`/resumes/${resumeId}/matches`} className="text-sm font-medium text-primary hover:underline transition-colors flex items-center gap-1">
              Compare against jobs →
            </Link>
          )}
        </div>

        {isLoading && <div className="mt-8 flex justify-center"><p className="text-sm text-muted-foreground animate-pulse">Loading analysis data…</p></div>}
        {error && (
          <div role="alert" className="mt-6 rounded-md bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {resume && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-6 mb-6">
            <div>
              <h1 className="text-2xl font-bold text-foreground tracking-tight">{resume.original_filename}</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Uploaded {new Date(resume.created_at).toLocaleDateString()}
              </p>
            </div>
            <StatusBadge status={resume.status} />
          </div>
        )}

        {resume?.status === "pending" || resume?.status === "processing" ? (
          <Card className="mt-8 shadow-none bg-muted/20 border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
              <p className="text-sm text-muted-foreground">
                Analysis is still running. Refresh this page in a moment.
              </p>
            </CardContent>
          </Card>
        ) : null}

        {resume?.status === "failed" && (
          <Card className="mt-8 bg-destructive/5 border-destructive/20 shadow-none">
            <CardContent className="py-8 text-center">
              <p className="text-sm font-medium text-destructive">
                {resume.failure_reason ?? "Analysis failed."}
              </p>
            </CardContent>
          </Card>
        )}

        {analysis && (
          <div className="space-y-6 animate-fade-in-up">
            <div className="grid gap-6 md:grid-cols-3">
              <Card className="md:col-span-1 shadow-sm relative overflow-hidden bg-primary text-primary-foreground border-none">
                <CardContent className="p-6 h-full flex flex-col justify-center relative z-10">
                  <div className="flex items-center justify-between mb-2">
                    <h2 className="text-sm font-semibold uppercase tracking-widest opacity-80">
                      Overall Score
                    </h2>
                  </div>
                  <div className="flex items-baseline gap-2 mt-2">
                    <p className="text-6xl font-bold tracking-tighter">{analysis.overall_score}</p>
                    <span className="text-xl font-normal opacity-70">/100</span>
                  </div>
                  <div className="mt-4 pt-4 border-t border-primary-foreground/20">
                    <p className="text-xs opacity-80 font-medium">
                      {analysis.analysis_mode === "ai_assisted" ? "AI-assisted Analysis" : "Deterministic Analysis"}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card className="md:col-span-2 shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Score Breakdown</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <ScoreBar label="ATS Optimization" score={analysis.ats_score} />
                    <ScoreBar label="Technical Skills" score={analysis.technical_score} />
                    <ScoreBar label="Skill Breadth" score={analysis.skill_score} />
                    <ScoreBar label="Experience" score={analysis.experience_score} />
                    <ScoreBar label="Projects" score={analysis.project_score} />
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card className="shadow-sm">
              <CardHeader className="pb-4 border-b">
                <CardTitle className="text-base font-semibold">
                  Detected Skills <span className="text-muted-foreground text-sm font-normal ml-2">({analysis.detected_skills.length})</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-6">
                <div className="flex flex-wrap gap-2">
                  {analysis.detected_skills.map((skill) => (
                    <span
                      key={skill.skill}
                      title={skill.evidence}
                      className="rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground border hover:bg-secondary/80 transition-colors"
                    >
                      {skill.skill}
                    </span>
                  ))}
                  {analysis.detected_skills.length === 0 && (
                    <p className="text-sm text-muted-foreground italic">No recognized skills detected.</p>
                  )}
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
              <Card className="shadow-sm border-l-4 border-l-green-500">
                <CardHeader className="pb-3 border-b border-border/50">
                  <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
                    Strengths
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                  {analysis.strengths.length > 0 ? (
                    <ul className="space-y-3">
                      {analysis.strengths.map((s, i) => (
                        <li key={i} className="flex gap-3 text-sm text-muted-foreground">
                          <span className="text-green-500 font-bold">•</span>
                          <span className="leading-relaxed">{s}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">No key strengths identified.</p>
                  )}
                </CardContent>
              </Card>

              <Card className="shadow-sm border-l-4 border-l-orange-500">
                <CardHeader className="pb-3 border-b border-border/50">
                  <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
                    Areas for Improvement
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                  {analysis.weaknesses.length > 0 ? (
                    <ul className="space-y-3">
                      {analysis.weaknesses.map((s, i) => (
                        <li key={i} className="flex gap-3 text-sm text-muted-foreground">
                          <span className="text-orange-500 font-bold">•</span>
                          <span className="leading-relaxed">{s}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">No weaknesses identified.</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {(analysis.missing_keywords.length > 0 || analysis.ats_issues.length > 0) && (
              <div className="grid gap-6 md:grid-cols-2">
                <Card className="shadow-sm">
                  <CardHeader className="pb-3 border-b">
                    <CardTitle className="text-base font-semibold">Missing Keywords</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-4">
                    <div className="flex flex-wrap gap-2">
                      {analysis.missing_keywords.length > 0 ? (
                        analysis.missing_keywords.map((kw) => (
                          <span key={kw} className="rounded-md bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300 px-2.5 py-1 text-xs font-medium border border-orange-200 dark:border-orange-800/50">
                            {kw}
                          </span>
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground">No critical missing keywords.</p>
                      )}
                    </div>
                  </CardContent>
                </Card>

                <Card className="shadow-sm">
                  <CardHeader className="pb-3 border-b">
                    <CardTitle className="text-base font-semibold">ATS Compatibility Issues</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-4">
                    {analysis.ats_issues.length > 0 ? (
                      <ul className="space-y-2">
                        {analysis.ats_issues.map((issue, i) => (
                          <li key={i} className="flex gap-2 text-sm text-muted-foreground items-start">
                            <span className="text-destructive mt-0.5">•</span>
                            <span>{issue}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No ATS issues found.</p>
                    )}
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
