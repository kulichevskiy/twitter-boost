"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export type Option = { value: string; label: string };

export function SimpleSelect({
  value,
  onChange,
  options,
  placeholder,
  className,
  size = "sm",
  disabled,
}: {
  value: string | null | undefined;
  onChange: (value: string | null) => void;
  options: Option[];
  placeholder?: string;
  className?: string;
  size?: "sm" | "default";
  disabled?: boolean;
}) {
  const items: Record<string, string> = Object.fromEntries(options.map((o) => [o.value, o.label]));
  return (
    <Select value={value ?? null} onValueChange={(v) => onChange((v as string | null) ?? null)} items={items} disabled={disabled}>
      <SelectTrigger size={size} className={className}>
        <SelectValue placeholder={placeholder ?? "—"} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
