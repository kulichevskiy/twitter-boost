"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { CopyIcon, RotateCcwIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, fetcher } from "@/lib/crm/api";
import { formatDate } from "@/lib/crm/format";
import type { SettingsOut } from "@/lib/crm/types";
import { BackendAlert } from "./backend-alert";
import { SimpleSelect } from "./simple-select";

type Values = Record<string, unknown>;

const SOURCE_LABELS: Record<string, string> = {
  twitterapi: "twitterapi.io",
  x: "Official X API",
  fake: "Synthetic (for tests)",
};

export function SettingsForm() {
  const { data, error, isLoading, mutate } = useSWR<SettingsOut>("/settings", fetcher);
  const [draft, setDraft] = useState<Values>({});
  const [saving, setSaving] = useState(false);
  const sp = useSearchParams();

  useEffect(() => {
    const x = sp.get("x");
    const xe = sp.get("x_error");
    if (x === "connected") toast.success("X connected");
    if (xe) toast.error(`X: ${xe}`);
    if (x || xe) window.history.replaceState(null, "", "/crm/settings");
  }, [sp]);

  if (error) return <BackendAlert error={error} />;
  if (isLoading || !data) return <Skeleton className="h-96 rounded-xl" />;

  const value = (k: string) => (k in draft ? draft[k] : data.values[k]);
  const set = (k: string, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));
  const dirty = Object.keys(draft).length > 0;

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/settings", { values: draft });
      setDraft({});
      toast.success("Settings saved");
      void mutate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const reset = async (k: string) => {
    await api.put("/settings", { values: { [k]: null } });
    setDraft((d) => {
      const n = { ...d };
      delete n[k];
      return n;
    });
    toast.success("Reset to .env");
    void mutate();
  };

  const connectX = async () => {
    try {
      const { url } = await api.get<{ url: string }>("/auth/x/start");
      window.location.href = url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    }
  };

  const Field = ({ k, label, hint, type = "text", className }: { k: string; label: string; hint?: string; type?: string; className?: string }) => (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <div className="flex items-center gap-2">
        <Label htmlFor={`s-${k}`}>{label}</Label>
        <Override k={k} />
      </div>
      <Input
        id={`s-${k}`}
        type={type}
        value={String(value(k) ?? "")}
        onChange={(e) => set(k, type === "number" ? Number(e.target.value) : e.target.value)}
        placeholder={type === "password" ? "not set" : undefined}
        autoComplete="off"
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );

  const Override = ({ k }: { k: string }) =>
    data.overrides.includes(k) ? (
      <span className="inline-flex items-center gap-1">
        <Badge variant="outline" className="text-[10px]">
          from DB
        </Badge>
        <Button size="icon-xs" variant="ghost" aria-label="Reset to .env" title="Reset to .env" onClick={() => void reset(k)}>
          <RotateCcwIcon />
        </Button>
      </span>
    ) : null;

  const sourceOptions = data.sources.map((s) => ({ value: s, label: SOURCE_LABELS[s] ?? s }));
  const cfg = data.configured;
  const provider = String(value("analysis_provider") ?? "claude_cli");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <Button size="sm" disabled={!dirty || saving} onClick={() => void save()}>
          Save{dirty ? ` (${Object.keys(draft).length})` : ""}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <Badge variant={cfg.my_handle ? "secondary" : "destructive"}>handle {cfg.my_handle ? "set" : "missing"}</Badge>
        <Badge variant={cfg.twitterapi ? "secondary" : "outline"}>twitterapi.io {cfg.twitterapi ? "ok" : "no key"}</Badge>
        <Badge variant={cfg.x ? "secondary" : "outline"}>X API {cfg.x ? "connected" : cfg.x_app ? "not connected" : "no app"}</Badge>
        <Badge variant={provider === "anthropic_api" && !cfg.anthropic ? "outline" : "secondary"}>
          analysis: {provider === "claude_cli" ? "Claude Code CLI" : provider === "codex_cli" ? "Codex CLI" : cfg.anthropic ? "Anthropic API" : "API key missing"}
        </Badge>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Account & sources</CardTitle>
            <CardDescription>Whose account we track and where the data comes from</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field k="my_handle" label="My @handle" hint="Without @. Required for twitterapi.io; filled automatically when X is connected." />
            {(["source_lists", "source_tweets", "source_profiles"] as const).map((k) => (
              <div key={k} className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <Label>{k === "source_lists" ? "Followers / following lists" : k === "source_tweets" ? "Tweets" : "Profiles"}</Label>
                  <Override k={k} />
                </div>
                <SimpleSelect value={String(value(k) ?? "")} onChange={(v) => v && set(k, v)} options={sourceOptions} size="default" className="w-full" />
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              Recommendation: lists via the X API (owned reads are cheap and legit), tweets and profiles via twitterapi.io.
            </p>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Keys</CardTitle>
            <CardDescription>Stored in the backend SQLite. Can also be set in backend/.env</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field k="twitterapi_io_key" label="twitterapi.io API key" type="password" hint="twitterapi.io → Dashboard → API key" />
            <Field k="anthropic_api_key" label="Anthropic API key" type="password" hint="console.anthropic.com" />
            <Field k="x_client_id" label="X OAuth 2.0 Client ID" hint="developer.x.com → App → Keys and tokens → OAuth 2.0" />
            <Field k="x_client_secret" label="X OAuth 2.0 Client Secret" type="password" hint="For confidential apps. Leave empty for a public client." />
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>X connection</CardTitle>
            <CardDescription>OAuth 2.0 with PKCE, scopes: tweet.read users.read follows.read offline.access</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label>Callback URL for the X developer portal</Label>
              <div className="flex gap-1">
                <Input readOnly value={data.redirect_uri} className="font-mono text-xs" />
                <Button
                  size="icon"
                  variant="outline"
                  aria-label="Copy"
                  onClick={async () => {
                    await navigator.clipboard.writeText(data.redirect_uri);
                    toast.success("Copied");
                  }}
                >
                  <CopyIcon />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">Add this URL under App settings → User authentication settings → Callback URI.</p>
            </div>
            {data.x.connected ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/60 p-3">
                <div>
                  <div className="font-medium">Connected as @{data.x.handle ?? "?"}</div>
                  <div className="text-xs text-muted-foreground">
                    token valid until {formatDate(data.x.expires_at ?? null, true)}
                    {data.x.has_refresh_token ? ", refreshes automatically" : ", no refresh token"}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    await api.del("/auth/x");
                    toast.success("X disconnected");
                    void mutate();
                  }}
                >
                  Disconnect
                </Button>
              </div>
            ) : (
              <Button size="sm" disabled={!cfg.x_app} onClick={() => void connectX()}>
                Connect X
              </Button>
            )}
            {!cfg.x_app && <p className="text-xs text-muted-foreground">Save the Client ID first.</p>}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Sync schedule</CardTitle>
            <CardDescription>The worker queues syncs on its own</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label>Mode</Label>
                <Override k="sync_schedule_mode" />
              </div>
              <SimpleSelect
                value={String(value("sync_schedule_mode") ?? "daily")}
                onChange={(v) => v && set("sync_schedule_mode", v)}
                options={[
                  { value: "daily", label: "Daily at a set time" },
                  { value: "interval", label: "Every N hours" },
                  { value: "off", label: "Off (manual only)" },
                ]}
                size="default"
                className="w-full"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field k="sync_daily_time" label="Time (local)" hint="HH:MM" />
              <Field k="sync_interval_hours" label="Interval, hours" type="number" />
            </div>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Pipeline & sync</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <Field k="followback_deadline_days" label="Wait for follow-back, days" type="number" />
            <Field k="unfollow_confirmations" label="Unfollow confirmations" type="number" hint="Consecutive syncs a person must be missing from the list" />
            <Field k="count_tolerance_pct" label="Count tolerance, %" type="number" hint="Above this the sync is marked suspicious" />
            <Field k="count_tolerance_abs" label="Count tolerance, records" type="number" />
            <Field k="profile_refresh_days" label="Refresh profiles older than, days" type="number" />
            <Field k="profile_refresh_batch" label="Max profiles per sync" type="number" />
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Analysis</CardTitle>
            <CardDescription>Which model we ask, and what we ask it</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label>Provider</Label>
                <Override k="analysis_provider" />
              </div>
              <SimpleSelect
                value={String(value("analysis_provider") ?? "claude_cli")}
                onChange={(v) => v && set("analysis_provider", v)}
                options={[
                  { value: "claude_cli", label: "Claude Code CLI (Anthropic subscription)" },
                  { value: "codex_cli", label: "Codex CLI (ChatGPT subscription)" },
                  { value: "anthropic_api", label: "Anthropic API (key, pay per token)" },
                ]}
                size="default"
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                CLI providers use the login on this machine (`claude /login`, `codex login`); no API key needed.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field k="analysis_model" label="Model" hint="Empty = provider default; for claude: opus / sonnet" />
              <Field k="analysis_tweets" label="Tweets per analysis" type="number" />
              <Field k="claude_cli_path" label="claude path" hint="If not on the worker's PATH" />
              <Field k="codex_cli_path" label="codex path" />
              <Field k="analysis_timeout_seconds" label="Analysis timeout, s" type="number" />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="s-replies"
                checked={Boolean(value("analysis_include_replies"))}
                onCheckedChange={(c) => set("analysis_include_replies", c)}
              />
              <Label htmlFor="s-replies">Fetch and analyze replies</Label>
              <Override k="analysis_include_replies" />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label htmlFor="s-goal">My goal</Label>
                <Override k="analysis_goal" />
              </div>
              <Textarea id="s-goal" rows={6} value={String(value("analysis_goal") ?? "")} onChange={(e) => set("analysis_goal", e.target.value)} />
              <p className="text-xs text-muted-foreground">Goes into the prompt. Changing it invalidates cached analyses.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
