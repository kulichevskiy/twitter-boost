"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "cn";

const items = [
  { href: "/course", label: "Курс" },
  { href: "/crm", label: "CRM" },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-1">
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-md px-2.5 py-1 text-sm transition-colors hover:bg-muted hover:text-foreground",
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
