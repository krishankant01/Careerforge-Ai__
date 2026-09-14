import { api } from "./api";
import type { Job, JobMatch, JobMatchWithJob } from "../types/job";

export async function createJob(rawDescription: string): Promise<Job> {
  const { data } = await api.post<Job>("/jobs", { raw_description: rawDescription });
  return data;
}

export async function listJobs(): Promise<Job[]> {
  const { data } = await api.get<Job[]>("/jobs");
  return data;
}

export async function getJob(jobId: string): Promise<Job> {
  const { data } = await api.get<Job>(`/jobs/${jobId}`);
  return data;
}

export async function matchJobToResume(jobId: string, resumeId: string): Promise<JobMatch> {
  const { data } = await api.post<JobMatch>(`/jobs/${jobId}/match`, { resume_id: resumeId });
  return data;
}

export async function listMatchesForResume(resumeId: string): Promise<JobMatchWithJob[]> {
  const { data } = await api.get<JobMatchWithJob[]>(`/resumes/${resumeId}/matches`);
  return data;
}
