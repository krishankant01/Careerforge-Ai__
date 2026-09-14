import type { SkillMatch } from "../types/job";

const STYLES: Record<SkillMatch["match_type"], string> = {
  exact: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
  inferred: "bg-sky-500/20 text-sky-400 border border-sky-500/30",
  semantic: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  missing: "bg-red-500/20 text-red-400 border border-red-500/30",
};

const LABELS: Record<SkillMatch["match_type"], string> = {
  exact: "Exact",
  inferred: "Inferred",
  semantic: "Semantic",
  missing: "Missing",
};

export function SkillMatchRow({ match }: { match: SkillMatch }) {
  return (
    <div
      title={match.reasoning}
      className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-4 py-3 hover:bg-white/5 transition-colors"
    >
      <div>
        <span className="text-sm font-semibold text-slate-200">{match.skill}</span>
        {match.matched_resume_skill && match.matched_resume_skill !== match.skill && (
          <span className="ml-2 text-xs text-slate-400">via <span className="text-slate-300 font-medium">{match.matched_resume_skill}</span></span>
        )}
        <span className="ml-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {match.requirement_level}
        </span>
      </div>
      <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] uppercase font-bold tracking-wider ${STYLES[match.match_type]}`}>
        {LABELS[match.match_type]}
      </span>
    </div>
  );
}
