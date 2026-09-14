export type JobStatus = "pending" | "processing" | "completed" | "failed";
export type MatchType = "exact" | "inferred" | "semantic" | "missing";
export type RequirementLevel = "required" | "preferred";

export interface Job {
  id: string;
  status: JobStatus;
  failure_reason: string | null;
  title: string | null;
  company: string | null;
  required_skills: string[] | null;
  preferred_skills: string[] | null;
  responsibilities: string[] | null;
  experience_requirement: string | null;
  education_requirement: string | null;
  parse_mode: "deterministic" | "ai_assisted" | null;
  created_at: string;
  updated_at: string;
}

export interface SkillMatch {
  skill: string;
  requirement_level: RequirementLevel;
  match_type: MatchType;
  matched_resume_skill: string | null;
  confidence: number;
  reasoning: string;
}

export interface JobMatch {
  id: string;
  job_id: string;
  resume_id: string;
  compatibility_score: number;
  required_coverage_score: number;
  preferred_coverage_score: number;
  skill_matches: SkillMatch[];
  score_explanation: Record<string, unknown>;
  semantic_mode: "deterministic" | "ai_assisted";
  created_at: string;
}

export interface JobMatchWithJob extends JobMatch {
  job_title: string | null;
  job_company: string | null;
}
