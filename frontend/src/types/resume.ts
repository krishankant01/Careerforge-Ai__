export type ResumeStatus = "pending" | "processing" | "completed" | "failed";

export interface Resume {
  id: string;
  original_filename: string;
  file_type: "pdf" | "docx";
  file_size_bytes: number;
  status: ResumeStatus;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResumeSection {
  section_type: string;
  order_index: number;
  content: string;
}

export interface ResumeDetail extends Resume {
  sections: ResumeSection[];
}

export interface DetectedSkill {
  skill: string;
  category: string;
  tier: number;
  evidence: string;
  line_number: number;
}

export interface ResumeAnalysis {
  id: string;
  resume_id: string;
  overall_score: number;
  ats_score: number;
  technical_score: number;
  experience_score: number;
  project_score: number;
  skill_score: number;
  score_explanations: Record<string, unknown>;
  detected_skills: DetectedSkill[];
  missing_keywords: string[];
  ats_issues: string[];
  strengths: string[];
  weaknesses: string[];
  // "deterministic" = rule-based only (no AI provider configured, or the
  // AI call failed). "ai_assisted" = experience/project scores and
  // narrative feedback came from the configured LLM.
  analysis_mode: "deterministic" | "ai_assisted";
  created_at: string;
}
