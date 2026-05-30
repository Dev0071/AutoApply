import { cn, scoreBg } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

interface FitScorePillProps {
  score: number;
  showBar?: boolean;
  className?: string;
}

function scoreBarColor(score: number) {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-red-500";
}

export function FitScorePill({ score, showBar = false, className }: FitScorePillProps) {
  return (
    <div className={cn("inline-flex flex-col gap-1 min-w-[48px]", className)}>
      <span className={cn("text-xs font-semibold px-1.5 py-0.5 rounded", scoreBg(score))}>
        {Math.round(score)}%
      </span>
      {showBar && (
        <Progress
          value={score}
          className="h-1"
          fillClassName={scoreBarColor(score)}
        />
      )}
    </div>
  );
}

export function FitScoreInline({ score, className }: { score: number; className?: string }) {
  const cfg = score >= 80
    ? { text: "text-emerald-600", bar: "bg-emerald-400" }
    : score >= 60
    ? { text: "text-amber-600", bar: "bg-amber-400" }
    : { text: "text-red-500", bar: "bg-red-400" };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className={cn("text-xs font-semibold tabular-nums w-8 text-right", cfg.text)}>
        {Math.round(score)}%
      </span>
      <div className="w-16 h-1 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full", cfg.bar)}
          style={{ width: `${Math.round(score)}%` }}
        />
      </div>
    </div>
  );
}
