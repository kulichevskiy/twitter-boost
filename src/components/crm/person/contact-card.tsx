"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api } from "@/lib/crm/api";
import { daysSince, daysUntil, formatDate, STAGE_LABELS } from "@/lib/crm/format";
import type { ContactOut, Stage } from "@/lib/crm/types";
import { STAGES } from "@/lib/crm/types";
import { SimpleSelect } from "../simple-select";

export function ContactCard({ personId, contact, onChanged }: { personId: string; contact: ContactOut | null; onChanged: () => void }) {
  const [note, setNote] = useState(contact?.note ?? "");
  const [prevNote, setPrevNote] = useState(contact?.note ?? "");
  const [saving, setSaving] = useState(false);
  if ((contact?.note ?? "") !== prevNote) {
    setPrevNote(contact?.note ?? "");
    setNote(contact?.note ?? "");
  }

  const patch = async (body: Record<string, unknown>, ok = "Сохранено") => {
    setSaving(true);
    try {
      await api.patch(`/people/${personId}/contact`, body);
      toast.success(ok);
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setSaving(false);
    }
  };

  const waitingDays = contact?.followed_at ? daysSince(contact.followed_at) : null;
  const left = contact?.deadline_at ? daysUntil(contact.deadline_at) : null;

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Пайплайн</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label>Стадия</Label>
          <SimpleSelect
            value={contact?.stage ?? null}
            onChange={(v) => v && void patch({ stage: v as Stage }, `Стадия: ${STAGE_LABELS[v as Stage]}`)}
            options={STAGES.map((s) => ({ value: s, label: STAGE_LABELS[s] }))}
            placeholder="Не в пайплайне"
            size="default"
            className="w-full"
            disabled={saving}
          />
        </div>
        {contact?.overdue && (
          <Alert variant="destructive">
            <AlertDescription>
              Дедлайн прошёл {left !== null ? `${Math.abs(left)} дн. назад` : ""}. Ответного фоллоу нет: отфоловить или подождать?
            </AlertDescription>
          </Alert>
        )}
        {contact && (
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Зафоловил</dt>
            <dd className="tabular-nums">
              {formatDate(contact.followed_at)}
              {waitingDays !== null && contact.stage !== "followed_back" && <span className="text-muted-foreground"> · {waitingDays} дн.</span>}
            </dd>
            <dt className="text-muted-foreground">Общение</dt>
            <dd className="tabular-nums">{formatDate(contact.engaged_at)}</dd>
            <dt className="text-muted-foreground">Ответный фоллоу</dt>
            <dd className="tabular-nums">{formatDate(contact.followed_back_at)}</dd>
            <dt className="text-muted-foreground">Дедлайн</dt>
            <dd className="tabular-nums">
              {formatDate(contact.deadline_at)}
              {left !== null && left >= 0 && contact.stage !== "followed_back" && <span className="text-muted-foreground"> · ещё {left} дн.</span>}
            </dd>
          </dl>
        )}
        {contact && (contact.stage === "followed" || contact.stage === "engaged" || contact.stage === "no_response") && (
          <div className="flex flex-wrap gap-2">
            {contact.stage === "followed" && (
              <Button size="sm" variant="outline" disabled={saving} onClick={() => void patch({ stage: "engaged" }, "Отмечено: общаюсь")}>
                Прокомментировал
              </Button>
            )}
            <Button size="sm" variant="outline" disabled={saving} onClick={() => void patch({ stage: "followed_back" }, "Взаимно")}>
              Зафоловил в ответ
            </Button>
            <Button size="sm" variant="outline" disabled={saving} onClick={() => void patch({ stage: "unfollowed" }, "Отфоловлен")}>
              Отфоловил
            </Button>
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="contact-note">Заметка по контакту</Label>
          <Textarea id="contact-note" value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="Где познакомились, о чём говорили…" />
          {note !== (contact?.note ?? "") && (
            <Button size="sm" disabled={saving} onClick={() => void patch({ note })}>
              Сохранить заметку
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
