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
  x: "Официальный X API",
  fake: "Синтетика (для тестов)",
};

export function SettingsForm() {
  const { data, error, isLoading, mutate } = useSWR<SettingsOut>("/settings", fetcher);
  const [draft, setDraft] = useState<Values>({});
  const [saving, setSaving] = useState(false);
  const sp = useSearchParams();

  useEffect(() => {
    const x = sp.get("x");
    const xe = sp.get("x_error");
    if (x === "connected") toast.success("X подключён");
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
      toast.success("Настройки сохранены");
      void mutate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Ошибка");
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
    toast.success("Сброшено к .env");
    void mutate();
  };

  const connectX = async () => {
    try {
      const { url } = await api.get<{ url: string }>("/auth/x/start");
      window.location.href = url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Ошибка");
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
        placeholder={type === "password" ? "не задан" : undefined}
        autoComplete="off"
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );

  const Override = ({ k }: { k: string }) =>
    data.overrides.includes(k) ? (
      <span className="inline-flex items-center gap-1">
        <Badge variant="outline" className="text-[10px]">
          из базы
        </Badge>
        <Button size="icon-xs" variant="ghost" aria-label="Сбросить к .env" title="Сбросить к .env" onClick={() => void reset(k)}>
          <RotateCcwIcon />
        </Button>
      </span>
    ) : null;

  const sourceOptions = data.sources.map((s) => ({ value: s, label: SOURCE_LABELS[s] ?? s }));
  const cfg = data.configured;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Настройки</h1>
        <Button size="sm" disabled={!dirty || saving} onClick={() => void save()}>
          Сохранить{dirty ? ` (${Object.keys(draft).length})` : ""}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <Badge variant={cfg.my_handle ? "secondary" : "destructive"}>хендл {cfg.my_handle ? "задан" : "не задан"}</Badge>
        <Badge variant={cfg.twitterapi ? "secondary" : "outline"}>twitterapi.io {cfg.twitterapi ? "ок" : "нет ключа"}</Badge>
        <Badge variant={cfg.x ? "secondary" : "outline"}>X API {cfg.x ? "подключён" : cfg.x_app ? "не подключён" : "нет приложения"}</Badge>
        <Badge variant={cfg.anthropic ? "secondary" : "outline"}>Claude {cfg.anthropic ? "ок" : "нет ключа"}</Badge>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Аккаунт и источники</CardTitle>
            <CardDescription>Чей аккаунт отслеживаем и откуда брать данные</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field k="my_handle" label="Мой @handle" hint="Без @. Нужен для twitterapi.io; при подключении X заполняется сам." />
            {(["source_lists", "source_tweets", "source_profiles"] as const).map((k) => (
              <div key={k} className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <Label>{k === "source_lists" ? "Списки фолловеров/подписок" : k === "source_tweets" ? "Твиты" : "Профили"}</Label>
                  <Override k={k} />
                </div>
                <SimpleSelect value={String(value(k) ?? "")} onChange={(v) => v && set(k, v)} options={sourceOptions} size="default" className="w-full" />
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              Рекомендация: списки через X API (owned reads дёшевы и легальны), твиты и профили через twitterapi.io.
            </p>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Ключи</CardTitle>
            <CardDescription>Хранятся в SQLite бэкенда. Можно задать и в backend/.env</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field k="twitterapi_io_key" label="twitterapi.io API key" type="password" hint="twitterapi.io → Dashboard → API key" />
            <Field k="anthropic_api_key" label="Anthropic API key" type="password" hint="console.anthropic.com" />
            <Field k="x_client_id" label="X OAuth 2.0 Client ID" hint="developer.x.com → App → Keys and tokens → OAuth 2.0" />
            <Field k="x_client_secret" label="X OAuth 2.0 Client Secret" type="password" hint="Для confidential-приложений. Для public можно оставить пустым." />
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Подключение X</CardTitle>
            <CardDescription>OAuth 2.0 с PKCE, scopes: tweet.read users.read follows.read offline.access</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label>Callback URL для портала X</Label>
              <div className="flex gap-1">
                <Input readOnly value={data.redirect_uri} className="font-mono text-xs" />
                <Button
                  size="icon"
                  variant="outline"
                  aria-label="Копировать"
                  onClick={async () => {
                    await navigator.clipboard.writeText(data.redirect_uri);
                    toast.success("Скопировано");
                  }}
                >
                  <CopyIcon />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">Добавь этот адрес в App settings → User authentication settings → Callback URI.</p>
            </div>
            {data.x.connected ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/60 p-3">
                <div>
                  <div className="font-medium">Подключён как @{data.x.handle ?? "?"}</div>
                  <div className="text-xs text-muted-foreground">
                    токен до {formatDate(data.x.expires_at ?? null, true)}
                    {data.x.has_refresh_token ? ", обновляется автоматически" : ", без refresh token"}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    await api.del("/auth/x");
                    toast.success("X отключён");
                    void mutate();
                  }}
                >
                  Отключить
                </Button>
              </div>
            ) : (
              <Button size="sm" disabled={!cfg.x_app} onClick={() => void connectX()}>
                Подключить X
              </Button>
            )}
            {!cfg.x_app && <p className="text-xs text-muted-foreground">Сначала сохрани Client ID.</p>}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Расписание синка</CardTitle>
            <CardDescription>Воркер сам ставит синк в очередь</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label>Режим</Label>
                <Override k="sync_schedule_mode" />
              </div>
              <SimpleSelect
                value={String(value("sync_schedule_mode") ?? "daily")}
                onChange={(v) => v && set("sync_schedule_mode", v)}
                options={[
                  { value: "daily", label: "Раз в день в заданное время" },
                  { value: "interval", label: "Каждые N часов" },
                  { value: "off", label: "Выключено (только вручную)" },
                ]}
                size="default"
                className="w-full"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field k="sync_daily_time" label="Время (локальное)" hint="ЧЧ:ММ" />
              <Field k="sync_interval_hours" label="Интервал, ч" type="number" />
            </div>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Пайплайн и синк</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <Field k="followback_deadline_days" label="Ждать ответного фоллоу, дней" type="number" />
            <Field k="unfollow_confirmations" label="Подтверждений отписки" type="number" hint="Сколько синков подряд человека нет в списке" />
            <Field k="count_tolerance_pct" label="Допуск по счётчику, %" type="number" hint="Больше — синк помечается подозрительным" />
            <Field k="count_tolerance_abs" label="Допуск, записей" type="number" />
            <Field k="profile_refresh_days" label="Обновлять профили старше, дней" type="number" />
            <Field k="profile_refresh_batch" label="Профилей за синк, макс." type="number" />
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Анализ</CardTitle>
            <CardDescription>Через что и о чём спрашиваем модель</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label>Провайдер</Label>
                <Override k="analysis_provider" />
              </div>
              <SimpleSelect
                value={String(value("analysis_provider") ?? "claude_cli")}
                onChange={(v) => v && set("analysis_provider", v)}
                options={[
                  { value: "claude_cli", label: "Claude Code CLI (подписка Anthropic)" },
                  { value: "codex_cli", label: "Codex CLI (подписка ChatGPT)" },
                  { value: "anthropic_api", label: "Anthropic API (ключ, оплата за токены)" },
                ]}
                size="default"
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                CLI-варианты используют логин на этой машине (`claude /login`, `codex login`), ключ не нужен.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field k="analysis_model" label="Модель" hint="Пусто = модель провайдера по умолчанию; для claude: opus / sonnet" />
              <Field k="analysis_tweets" label="Твитов на разбор" type="number" />
              <Field k="claude_cli_path" label="Путь к claude" hint="Если не в PATH у воркера" />
              <Field k="codex_cli_path" label="Путь к codex" />
              <Field k="analysis_timeout_seconds" label="Таймаут разбора, сек" type="number" />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="s-replies"
                checked={Boolean(value("analysis_include_replies"))}
                onCheckedChange={(c) => set("analysis_include_replies", c)}
              />
              <Label htmlFor="s-replies">Загружать и анализировать реплаи</Label>
              <Override k="analysis_include_replies" />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label htmlFor="s-goal">Моя цель</Label>
                <Override k="analysis_goal" />
              </div>
              <Textarea id="s-goal" rows={6} value={String(value("analysis_goal") ?? "")} onChange={(e) => set("analysis_goal", e.target.value)} />
              <p className="text-xs text-muted-foreground">Попадает в промпт. Изменение цели сбрасывает кэш разборов.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
