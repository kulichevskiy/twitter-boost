import { Suspense } from "react";
import type { Metadata } from "next";
import { CrmNav } from "@/components/crm/crm-nav";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: { default: "CRM", template: "%s — CRM" },
};

export default function CrmLayout({ children }: LayoutProps<"/crm">) {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-4">
      <Suspense fallback={<div className="h-8" />}>
        <CrmNav />
      </Suspense>
      {children}
      <Toaster position="bottom-right" />
    </div>
  );
}
