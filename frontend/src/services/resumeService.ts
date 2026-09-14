import { api } from "./api";
import type { Resume, ResumeAnalysis, ResumeDetail } from "../types/resume";

export async function uploadResume(file: File): Promise<Resume> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<Resume>("/resumes/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listResumes(): Promise<Resume[]> {
  const { data } = await api.get<Resume[]>("/resumes");
  return data;
}

export async function getResume(resumeId: string): Promise<ResumeDetail> {
  const { data } = await api.get<ResumeDetail>(`/resumes/${resumeId}`);
  return data;
}

export async function getResumeAnalysis(resumeId: string): Promise<ResumeAnalysis> {
  const { data } = await api.get<ResumeAnalysis>(`/resumes/${resumeId}/analysis`);
  return data;
}
