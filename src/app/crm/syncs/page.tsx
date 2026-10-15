import { Suspense } from "react";
import type { Metadata } from "next";
import { Skeleton } from "@/components/ui/skeleton";
import { SyncsView } from "@/components/crm/syncs-view";

export const metadata: Metadata = { title: "Синки" };

export default function SyncsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <SyncsView />
    </Suspense>
  );
}
