import { Suspense } from "react";
import type { Metadata } from "next";
import { Skeleton } from "@/components/ui/skeleton";
import { PipelineBoard } from "@/components/crm/pipeline-board";

export const metadata: Metadata = { title: "Пайплайн" };

export default function PipelinePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <PipelineBoard />
    </Suspense>
  );
}
