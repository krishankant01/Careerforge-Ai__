import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "../components/StatusBadge";
import { ScoreBar } from "../components/ScoreBar";
import { SkillMatchRow } from "../components/SkillMatchRow";
import { extractErrorMessage } from "../services/api";
import { createJob, getJob, listJobs, matchJobToResume } from "../services/jobService";
import { listResumes } from "../services/resumeService";
import type { Job, JobMatch } from "../types/job";
import type { Resume } from "../types/resume";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import toast from "react-hot-toast";
import { Briefcase, Building, CheckCircle2 } from "lucide-react";

export default function JobAnalyzer() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [match, setMatch] = useState<JobMatch | null>(null);
  const [isMatching, setIsMatching] = useState(false);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await listJobs());
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setIsLoadingJobs(false);
    }
  }, []);

  useEffect(() => {
    refreshJobs();
    listResumes()
      .then((r) => setResumes(r.filter((resume) => resume.status === "completed")))
      .catch(() => {});
  }, [refreshJobs]);

  async function handleSubmit() {
    if (description.trim().length < 50) {
      toast.error("Paste the full job description (at least 50 characters).");
      return;
    }
    
    setIsSubmitting(true);
    const toastId = toast.loading("Analyzing job description...");
    try {
      const job = await createJob(description);
      setDescription("");
      setSelectedJob(job);
      setMatch(null);
      await refreshJobs();
      toast.success("Job analyzed successfully!", { id: toastId });
    } catch (err) {
      toast.error(extractErrorMessage(err), { id: toastId });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function openJob(jobId: string) {
    setMatch(null);
    try {
      setSelectedJob(await getJob(jobId));
    } catch (err) {
      toast.error(extractErrorMessage(err));
    }
  }

  async function runMatch() {
    if (!selectedJob || !selectedResumeId) return;
    setIsMatching(true);
    const toastId = toast.loading("Matching resume to job...");
    try {
      setMatch(await matchJobToResume(selectedJob.id, selectedResumeId));
      toast.success("Match complete!", { id: toastId });
    } catch (err) {
      toast.error(extractErrorMessage(err), { id: toastId });
    } finally {
      setIsMatching(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Job Analyzer</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Extract skills from job descriptions and see how well your resume matches.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Left: paste + job list */}
        <div className="md:col-span-1 space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-base font-semibold">Analyze New Job</CardTitle>
              <CardDescription className="text-xs">Paste the job posting below.</CardDescription>
            </CardHeader>
            <CardContent className="pt-4">
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Paste the full job description here…"
                rows={6}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary focus-visible:border-primary resize-none transition-colors"
              />
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="w-full mt-3"
              >
                {isSubmitting ? "Analyzing…" : "Analyze Description"}
              </Button>
            </CardContent>
          </Card>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight text-foreground">Tracked Jobs</h2>
            
            {isLoadingJobs ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
              </div>
            ) : jobs.length === 0 ? (
              <Card className="bg-muted/10 border-dashed shadow-none">
                <CardContent className="flex flex-col items-center justify-center py-6 text-center">
                  <Briefcase className="w-6 h-6 text-muted-foreground mb-2 opacity-50" />
                  <p className="text-xs font-medium text-foreground">No jobs tracked</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-2">
                {jobs.map((job) => (
                  <button
                    key={job.id}
                    onClick={() => openJob(job.id)}
                    className={`flex items-center justify-between p-3 rounded-md border transition-colors text-left ${
                      selectedJob?.id === job.id 
                        ? "bg-primary/5 border-primary" 
                        : "bg-card border-border hover:border-primary/50 hover:bg-muted/30"
                    }`}
                  >
                    <div className="truncate pr-3">
                      <span className={`text-sm font-medium truncate block ${selectedJob?.id === job.id ? 'text-primary' : 'text-foreground'}`}>
                        {job.title ?? "Untitled posting"}
                      </span>
                      {job.company && <span className="text-xs text-muted-foreground mt-0.5 block">{job.company}</span>}
                    </div>
                    <StatusBadge status={job.status} />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: selected job detail + match */}
        <div className="md:col-span-2 space-y-6">
          {!selectedJob ? (
            <Card className="h-full border-dashed bg-muted/10 flex items-center justify-center min-h-[400px] shadow-none">
              <CardContent className="flex flex-col items-center justify-center text-center">
                <div className="p-3 rounded-full bg-muted mb-3">
                  <Building className="w-8 h-8 text-muted-foreground opacity-50" />
                </div>
                <h3 className="text-lg font-medium text-foreground mb-1">Select a Job</h3>
                <p className="text-sm text-muted-foreground max-w-[280px]">Choose a job from the list or analyze a new one to see extracted skills and matches.</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="shadow-sm overflow-hidden flex flex-col min-h-[400px]">
              <CardHeader className="border-b bg-muted/20">
                <div className="flex items-start justify-between mb-1">
                  <div>
                    <CardTitle className="text-lg text-foreground">{selectedJob.title ?? "Untitled posting"}</CardTitle>
                    {selectedJob.company && <CardDescription className="flex items-center gap-1.5 mt-1 text-muted-foreground text-sm"><Building className="w-3.5 h-3.5"/> {selectedJob.company}</CardDescription>}
                  </div>
                  <StatusBadge status={selectedJob.status} />
                </div>
              </CardHeader>
              <CardContent className="pt-6 flex-1">
                {selectedJob.status === "failed" && (
                  <div className="bg-destructive/10 text-destructive p-3 rounded-md text-sm border border-destructive/20">
                    {selectedJob.failure_reason}
                  </div>
                )}

                {selectedJob.status === "completed" && (
                  <div className="space-y-6">
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-primary"/> Required Skills
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedJob.required_skills?.map((s) => (
                          <span key={s} className="rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground border border-border">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-primary opacity-60"/> Preferred Skills
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedJob.preferred_skills?.map((s) => (
                          <span key={s} className="rounded-md bg-transparent px-2.5 py-1 text-xs text-muted-foreground border border-dashed border-border">
                            {s}
                          </span>
                        ))}
                        {selectedJob.preferred_skills?.length === 0 && (
                          <span className="text-sm text-muted-foreground italic">None detected</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
              {selectedJob.status === "completed" && (
                <CardFooter className="flex-col items-start border-t bg-muted/10 pt-5">
                  <h4 className="text-sm font-semibold text-foreground mb-3">Match Against Your Resume</h4>
                  <div className="flex w-full gap-3">
                    <select
                      value={selectedResumeId}
                      onChange={(e) => setSelectedResumeId(e.target.value)}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary shadow-sm"
                    >
                      <option value="">Choose a resume…</option>
                      {resumes.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.original_filename}
                        </option>
                      ))}
                    </select>
                    <Button
                      onClick={runMatch}
                      disabled={!selectedResumeId || isMatching}
                      className="whitespace-nowrap"
                    >
                      {isMatching ? "Matching…" : "Run Match"}
                    </Button>
                  </div>
                </CardFooter>
              )}
            </Card>
          )}

          {match && (
            <Card className="shadow-md border-primary/20 animate-fade-in-up">
              <CardHeader className="bg-primary/5 border-b border-primary/10 pb-4">
                <CardTitle className="text-sm font-semibold text-foreground">Match Results</CardTitle>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-4xl font-bold tracking-tight text-primary">{match.compatibility_score}%</span>
                  <span className="text-xs font-medium text-muted-foreground">Overall Compatibility</span>
                </div>
              </CardHeader>
              <CardContent className="pt-6 space-y-6">
                <div className="space-y-4">
                  <ScoreBar label="Required Skills Coverage" score={match.required_coverage_score} />
                  <ScoreBar label="Preferred Skills Coverage" score={match.preferred_coverage_score} />
                </div>
                
                <div className="border-t pt-5">
                  <h4 className="text-sm font-semibold text-foreground mb-3">Skill Breakdown</h4>
                  <div className="space-y-2">
                    {match.skill_matches.map((m) => (
                      <SkillMatchRow key={`${m.requirement_level}-${m.skill}`} match={m} />
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
