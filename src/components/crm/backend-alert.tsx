import { AlertTriangleIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ApiError } from "@/lib/crm/api";

export function BackendAlert({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : null;
  const unreachable = e?.unreachable ?? false;
  return (
    <Alert variant="destructive">
      <AlertTriangleIcon />
      <AlertTitle>{unreachable ? "Бэкенд недоступен" : "Ошибка запроса"}</AlertTitle>
      <AlertDescription>
        {unreachable ? (
          <>
            Запусти API: <code className="rounded bg-muted px-1 py-0.5 text-xs">cd backend && uv run crm serve</code> и
            воркер: <code className="rounded bg-muted px-1 py-0.5 text-xs">uv run crm worker</code>.
          </>
        ) : (
          (e?.message ?? String(error))
        )}
      </AlertDescription>
    </Alert>
  );
}
