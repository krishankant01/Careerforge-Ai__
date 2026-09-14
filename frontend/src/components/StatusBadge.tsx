import type { ResumeStatus } from "../types/resume";

const STYLES: Record<ResumeStatus, string> = {
  pending: "bg-slate-500/20 text-slate-300 border border-slate-500/30",
  processing: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  completed: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
  failed: "bg-red-500/20 text-red-400 border border-red-500/30",
};

export function StatusBadge({ status }: { status: ResumeStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${STYLES[status]}`}>
      {status}
    </span>
  );
}
