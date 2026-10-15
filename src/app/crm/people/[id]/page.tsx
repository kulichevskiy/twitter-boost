import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { PersonView } from "@/components/crm/person/person-view";

export default function PersonPage({ params }: PageProps<"/crm/people/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <PersonContent params={params} />
    </Suspense>
  );
}

async function PersonContent({ params }: { params: PageProps<"/crm/people/[id]">["params"] }) {
  const { id } = await params;
  return <PersonView id={id} />;
}
