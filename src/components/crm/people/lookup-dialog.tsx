"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UserPlusIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/crm/api";
import { STAGE_LABELS } from "@/lib/crm/format";
import type { JobOut, Stage } from "@/lib/crm/types";
import { SimpleSelect } from "../simple-select";
import { useJob } from "../use-job";

export function LookupDialog() {
  const [open, setOpen] = useState(false);
  const [handle, setHandle] = useState("");
  const [stage, setStage] = useState<Stage>("candidate");
  const { start, running } = useJob();
  const router = useRouter();

  const submit = async () => {
    const h = handle.trim().replace(/^@/, "");
    if (!h) return;
    const job = await start(() => api.post<JobOut>("/people/lookup", { handle: h, stage }), {
      pending: `Ищу @${h}…`,
      success: () => `@${h} добавлен`,
    });
    if (job?.status === "done" && job.result?.person_id) {
      setOpen(false);
      setHandle("");
      router.push(`/crm/people/${String(job.result.person_id)}`);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" variant="outline" />}>
        <UserPlusIcon /> Добавить по @handle
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Добавить человека</DialogTitle>
          <DialogDescription>Профиль подтянется из источника данных (платный запрос) и попадёт в пайплайн.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="lookup-handle">Хендл</Label>
            <Input id="lookup-handle" autoFocus value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@handle" />
          </div>
          <div className="space-y-1.5">
            <Label>Стадия</Label>
            <SimpleSelect
              value={stage}
              onChange={(v) => setStage((v as Stage) ?? "candidate")}
              options={Object.entries(STAGE_LABELS).map(([value, label]) => ({ value, label }))}
              size="default"
              className="w-full"
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={running || !handle.trim()}>
              Добавить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
