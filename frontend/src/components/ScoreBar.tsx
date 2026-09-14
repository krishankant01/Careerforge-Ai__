interface ScoreBarProps {
  label: string;
  score: number;
  helpText?: string;
}

function colorForScore(score: number): string {
  if (score >= 75) return "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)]";
  if (score >= 50) return "bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.8)]";
  return "bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)]";
}

export function ScoreBar({ label, score, helpText }: ScoreBarProps) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-slate-300">{label}</span>
        <span className="text-sm font-bold text-white">{score}/100</span>
      </div>
      <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-white/10 border border-white/5">
        <div
          className={`h-full rounded-full ${colorForScore(score)} transition-all duration-500 ease-out`}
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
      {helpText && <p className="mt-1.5 text-xs text-slate-400 font-medium">{helpText}</p>}
    </div>
  );
}
