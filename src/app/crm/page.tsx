import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Overview } from "@/components/crm/overview";

export default function CrmOverviewPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <Overview />
    </Suspense>
  );
}
