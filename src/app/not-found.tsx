import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-start gap-3 py-10">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <div className="flex gap-2">
        <Button render={<Link href="/crm" />} variant="outline">
          Open CRM
        </Button>
      </div>
    </div>
  );
}
