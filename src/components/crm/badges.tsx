import { Badge } from "@/components/ui/badge";
import { STAGE_CLASSES, STAGE_LABELS } from "@/lib/crm/format";
import type { Stage } from "@/lib/crm/types";
import { cn } from "cn";

export function StageBadge({ stage, className }: { stage: Stage | string | null | undefined; className?: string }) {
  if (!stage) return <span className="text-xs text-muted-foreground">—</span>;
  const s = stage as Stage;
  return (
    <Badge variant="outline" className={cn("border-transparent", STAGE_CLASSES[s] ?? "", className)}>
      {STAGE_LABELS[s] ?? stage}
    </Badge>
  );
}

export function RelationBadges({
  isFollower,
  isFollowing,
  className,
}: {
  isFollower: boolean;
  isFollowing: boolean;
  className?: string;
}) {
  if (!isFollower && !isFollowing) return <span className={cn("text-xs text-muted-foreground", className)}>нет связи</span>;
  return (
    <span className={cn("flex flex-wrap gap-1", className)}>
      {isFollower && (
        <Badge variant="outline" className="border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
          фолловит
        </Badge>
      )}
      {isFollowing && (
        <Badge variant="outline" className="border-transparent bg-blue-500/10 text-blue-700 dark:text-blue-300">
          я фоловлю
        </Badge>
      )}
    </span>
  );
}

export function ScoreDots({ score, className }: { score: number | null | undefined; className?: string }) {
  if (score === null || score === undefined) return <span className={cn("text-xs text-muted-foreground", className)}>—</span>;
  return (
    <span className={cn("inline-flex items-center gap-0.5", className)} title={`Оценка ${score} из 5`} aria-label={`Оценка ${score} из 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={cn(
            "size-2 rounded-full",
            i <= score ? (score >= 4 ? "bg-emerald-500" : score >= 3 ? "bg-amber-500" : "bg-red-400") : "bg-muted-foreground/20",
          )}
        />
      ))}
    </span>
  );
}
