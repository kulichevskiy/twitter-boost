"use client";

import { CopyIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { formatDate, personaLabel } from "@/lib/crm/format";
import type { AnalysisOut } from "@/lib/crm/types";
import { ScoreDots } from "../badges";

export function AnalysisCard({ analysis, count }: { analysis: AnalysisOut | null; count: number }) {
  if (!analysis) {
    return (
      <Empty className="rounded-xl ring-1 ring-foreground/10">
        <EmptyHeader>
          <EmptyTitle>Ещё не разобран</EmptyTitle>
          <EmptyDescription>Нажми «Разобрать»: подтянем твиты и попросим Claude оценить человека под твою цель.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  const r = analysis.result;
  const copy = async () => {
    await navigator.clipboard.writeText(r.opener);
    toast.success("Скопировано");
  };
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <ScoreDots score={r.relevance_score} />
        <span className="font-medium">{r.relevance_score} / 5</span>
        <Badge variant="secondary">{personaLabel(r.persona)}</Badge>
        <Badge variant="outline">{r.language}</Badge>
        <span className="ml-auto text-xs text-muted-foreground">
          {formatDate(analysis.created_at, true)} · {analysis.model} · {analysis.tweets_used} твитов
          {count > 1 && ` · разборов: ${count}`}
        </span>
      </div>
      <p className="text-base">{r.summary}</p>
      <div className="flex flex-wrap gap-1">
        {r.topics.map((t) => (
          <Badge key={t} variant="outline">
            {t}
          </Badge>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <section>
          <h3 className="mb-1 text-xs font-medium text-muted-foreground uppercase">Почему такая оценка</h3>
          <ul className="list-disc space-y-0.5 pl-5">
            {r.relevance_reasons.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-1 text-xs font-medium text-muted-foreground uppercase">Как ведёт себя в X</h3>
          <p>{r.engagement_style}</p>
          {r.red_flags.length > 0 && (
            <>
              <h3 className="mt-3 mb-1 text-xs font-medium text-red-600 uppercase dark:text-red-400">Настораживает</h3>
              <ul className="list-disc space-y-0.5 pl-5">
                {r.red_flags.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
      <section>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-xs font-medium text-muted-foreground uppercase">Зацепка для первого сообщения</h3>
          <Button size="xs" variant="ghost" onClick={() => void copy()}>
            <CopyIcon /> копировать
          </Button>
        </div>
        <blockquote className="rounded-lg bg-muted/60 p-3 whitespace-pre-line">{r.opener}</blockquote>
      </section>
    </div>
  );
}
