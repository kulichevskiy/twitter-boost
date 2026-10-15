"use client";

import { useState } from "react";
import { TrashIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/crm/api";
import { formatDate } from "@/lib/crm/format";
import type { NoteOut } from "@/lib/crm/types";

export function Notes({ personId, notes, onChanged }: { personId: string; notes: NoteOut[]; onChanged: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const add = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api.post(`/people/${personId}/notes`, { text: text.trim() });
      setText("");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder="New note" />
        <Button size="sm" type="submit" disabled={busy || !text.trim()}>
          Add
        </Button>
      </form>
      {notes.length === 0 ? (
        <p className="text-sm text-muted-foreground">No notes yet.</p>
      ) : (
        <ul className="divide-y">
          {notes.map((n) => (
            <li key={n.id} className="flex items-start gap-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="whitespace-pre-line">{n.text}</p>
                <div className="text-xs text-muted-foreground tabular-nums">{formatDate(n.created_at, true)}</div>
              </div>
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label="Delete"
                onClick={async () => {
                  await api.del(`/people/${personId}/notes/${n.id}`);
                  onChanged();
                }}
              >
                <TrashIcon />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
