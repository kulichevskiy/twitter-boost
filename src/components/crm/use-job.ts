"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { ApiError, pollJob } from "@/lib/crm/api";
import type { JobOut } from "@/lib/crm/types";

/**
 * Wraps "enqueue -> poll -> toast" for buttons that start backend jobs.
 * `start` returns the final job (or null on failure).
 */
export function useJob() {
  const [running, setRunning] = useState(false);

  const start = useCallback(
    async (
      enqueue: () => Promise<JobOut>,
      opts: { pending?: string; success?: (job: JobOut) => string; onDone?: (job: JobOut) => void } = {},
    ): Promise<JobOut | null> => {
      setRunning(true);
      const id = toast.loading(opts.pending ?? "В очереди…");
      try {
        const queued = await enqueue();
        const job = await pollJob(queued.id);
        if (job.status === "done") {
          toast.success(opts.success ? opts.success(job) : "Готово", { id });
          opts.onDone?.(job);
          return job;
        }
        toast.error(job.error ? `Ошибка: ${job.error}` : `Задача ${job.status}`, { id });
        return job;
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Не удалось запустить задачу", { id });
        return null;
      } finally {
        setRunning(false);
      }
    },
    [],
  );

  return { start, running };
}
