"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "cn";

const items = [
  { href: "/crm", label: "Overview", exact: true },
  { href: "/crm/people", label: "People" },
  { href: "/crm/pipeline", label: "Pipeline" },
  { href: "/crm/events", label: "Events" },
  { href: "/crm/syncs", label: "Syncs" },
  { href: "/crm/settings", label: "Settings" },
];

export function CrmNav() {
  const pathname = usePathname();
  return (
    <nav className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 text-sm">
      {items.map((item) => {
        const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "shrink-0 rounded-md px-2.5 py-1.5 transition-colors hover:bg-muted hover:text-foreground",
              active ? "bg-muted font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
