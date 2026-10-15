import { Suspense } from "react";
import type { Metadata } from "next";
import { Skeleton } from "@/components/ui/skeleton";
import { PeopleView } from "@/components/crm/people/people-view";

export const metadata: Metadata = { title: "People" };

export default function PeoplePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <PeopleView />
    </Suspense>
  );
}
