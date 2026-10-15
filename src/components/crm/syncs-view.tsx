"use client";

import { useState } from "react";
import useSWR from "swr";
import { RefreshCwIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, fetcher } from "@/lib/crm/api";
import { duration, formatDate, jobLabel, relativeTime } from "@/lib/crm/format";
import type { JobOut, SyncOut } from "@/lib/crm/types";
import { BackendAlert } from "./backend-alert";
import { SimpleSelect } from "./simple-select";
import { useJob } from "./use-job";

function SyncStatus({ s }: { s: SyncOut }) {
  const variant = s.status === "ok" ? "secondary" : s.status === "running" ? "outline" : "destructive";
  const badge = <Badge variant={variant}>{s.status}</Badge>;
  if (!s.error) return badge;
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="inline-flex" />}>{badge}</TooltipTrigger>
      <TooltipContent>{s.error}</TooltipContent>
    </Tooltip>
  );
}

function JobStatus({ j }: { j: JobOut }) {
  const variant = j.status === "done" ? "secondary" : j.status === "failed" ? "destructive" : "outline";
  const badge = <Badge variant={variant}>{j.status}</Badge>;
  if (!j.error) return badge;
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="inline-flex" />}>{badge}</TooltipTrigger>
      <TooltipContent className="max-w-md whitespace-pre-wrap">{j.error}</TooltipContent>
    </Tooltip>
  );
}

function describeJob(j: JobOut): string {
  const p = j.payload;
  if (j.type === "bulk") return `${String(p.action)} × ${Array.isArray(p.ids) ? p.ids.length : "filter"}`;
  if (p.person_id) return `person ${String(p.person_id)}`;
  if (p.handle) return `@${String(p.handle)}`;
  if (p.trigger) return String(p.trigger);
  return "";
}

export function SyncsView() {
  const [status, setStatus] = useState<string>("all");
  const jobsKey = status === "all" ? "/jobs?limit=100" : `/jobs?limit=100&status=${status}`;
  const syncs = useSWR<SyncOut[]>("/syncs?limit=50", fetcher, { refreshInterval: 10000 });
  const jobs = useSWR<JobOut[]>(jobsKey, fetcher, {
    refreshInterval: (d) => (d?.some((j) => j.status === "queued" || j.status === "running") ? 2000 : 15000),
  });
  const { start, running } = useJob();

  const refreshAll = () => {
    void syncs.mutate();
    void jobs.mutate();
  };

  if (syncs.error) return <BackendAlert error={syncs.error} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Syncs & queue</h1>
        <Button
          size="sm"
          disabled={running}
          onClick={() =>
            start(() => api.post<JobOut>("/syncs/run"), {
              pending: "Syncing…",
              success: (j) => `Sync ${String(j.result?.status)}`,
              onDone: refreshAll,
            })
          }
        >
          <RefreshCwIcon className={running ? "animate-spin" : ""} /> Sync now
        </Button>
      </div>

      <Card size="sm" className="py-0">
        <CardHeader className="pt-3">
          <CardTitle>Syncs</CardTitle>
          <CardDescription>Snapshots of the followers and following lists</CardDescription>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          {!syncs.data ? (
            <Skeleton className="m-4 h-32" />
          ) : syncs.data.length === 0 ? (
            <p className="px-4 pb-4 text-sm text-muted-foreground">No syncs yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>When</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Followers</TableHead>
                    <TableHead className="text-right">Following</TableHead>
                    <TableHead className="text-right">Profiles</TableHead>
                    <TableHead className="text-right">Requests</TableHead>
                    <TableHead className="text-right">Duration</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {syncs.data.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="tabular-nums">{s.id}</TableCell>
                      <TableCell className="whitespace-nowrap" title={s.started_at}>
                        {formatDate(s.started_at, true)}
                      </TableCell>
                      <TableCell>
                        <SyncStatus s={s} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {s.kind} · {s.source}
                      </TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        {s.followers_total ?? "—"}
                        {s.followers_expected !== null && s.followers_expected !== s.followers_total && (
                          <span className="text-muted-foreground"> / {s.followers_expected}</span>
                        )}
                        <span className="ml-1 text-xs text-muted-foreground">
                          +{s.added_followers} −{s.removed_followers}
                        </span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        {s.following_total ?? "—"}
                        {s.following_expected !== null && s.following_expected !== s.following_total && (
                          <span className="text-muted-foreground"> / {s.following_expected}</span>
                        )}
                        <span className="ml-1 text-xs text-muted-foreground">
                          +{s.added_following} −{s.removed_following}
                        </span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{s.profiles_refreshed}</TableCell>
                      <TableCell className="text-right tabular-nums">{s.requests}</TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">{duration(s.started_at, s.finished_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card size="sm" className="py-0">
        <CardHeader className="flex flex-row items-center justify-between pt-3">
          <div>
            <CardTitle>Jobs</CardTitle>
            <CardDescription>Tweets, analysis, profiles, bulk actions</CardDescription>
          </div>
          <SimpleSelect
            value={status}
            onChange={(v) => setStatus(v ?? "all")}
            options={[
              { value: "all", label: "All statuses" },
              { value: "queued,running", label: "Active" },
              { value: "failed", label: "Failed" },
              { value: "done", label: "Done" },
            ]}
            className="w-36"
          />
        </CardHeader>
        <CardContent className="px-0 pb-0">
          {jobs.error ? (
            <div className="p-4">
              <BackendAlert error={jobs.error} />
            </div>
          ) : !jobs.data ? (
            <Skeleton className="m-4 h-32" />
          ) : jobs.data.length === 0 ? (
            <p className="px-4 pb-4 text-sm text-muted-foreground">Empty.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>What</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Attempts</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.data.map((j) => (
                    <TableRow key={j.id}>
                      <TableCell className="tabular-nums">{j.id}</TableCell>
                      <TableCell>{jobLabel(j.type)}</TableCell>
                      <TableCell className="max-w-48 truncate text-muted-foreground">{describeJob(j)}</TableCell>
                      <TableCell>
                        <JobStatus j={j} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {j.attempts}/{j.max_attempts}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground" title={j.created_at}>
                        {relativeTime(j.created_at)}
                      </TableCell>
                      <TableCell className="max-w-64 truncate text-xs text-muted-foreground" title={j.result ? JSON.stringify(j.result) : ""}>
                        {j.result ? JSON.stringify(j.result) : j.error ? j.error.slice(0, 80) : ""}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap">
                        {(j.status === "failed" || j.status === "cancelled") && (
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={async () => {
                              await api.post(`/jobs/${j.id}/retry`);
                              toast.success("Job re-queued");
                              refreshAll();
                            }}
                          >
                            Retry
                          </Button>
                        )}
                        {j.status === "queued" && (
                          <Button
                            size="xs"
                            variant="ghost"
                            onClick={async () => {
                              await api.del(`/jobs/${j.id}`);
                              refreshAll();
                            }}
                          >
                            Cancel
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
