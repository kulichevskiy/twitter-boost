"use client";

import { useCallback, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { fetcher, peopleQuery } from "@/lib/crm/api";
import { parseFilter, serializeFilter } from "@/lib/crm/filters";
import type { Paginated, PeopleFilter, PersonOut } from "@/lib/crm/types";
import { BackendAlert } from "../backend-alert";
import { BulkToolbar } from "./bulk-toolbar";
import { FilterBar } from "./filter-bar";
import { LookupDialog } from "./lookup-dialog";
import { PeopleTable } from "./people-table";
import { SavedViews } from "./saved-views";

export function PeopleView() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const filter = useMemo(() => parseFilter(new URLSearchParams(sp.toString())), [sp]);
  const key = `/people?${peopleQuery(filter).toString()}`;
  const { data, error, isLoading, mutate } = useSWR<Paginated<PersonOut>>(key, fetcher, { keepPreviousData: true });
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const setFilter = useCallback(
    (f: PeopleFilter) => {
      const qs = serializeFilter(f).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname);
    },
    [router, pathname],
  );

  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const toggleAll = (checked: boolean) =>
    setSelected((s) => {
      const n = new Set(s);
      for (const p of data?.items ?? []) {
        if (checked) n.add(p.id);
        else n.delete(p.id);
      }
      return n;
    });

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const page = filter.page ?? 1;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">
          People {data && <span className="text-base font-normal text-muted-foreground tabular-nums">· {data.total}</span>}
        </h1>
        <div className="flex gap-2">
          <SavedViews filter={filter} onApply={setFilter} />
          <LookupDialog />
        </div>
      </div>
      <FilterBar filter={filter} onChange={setFilter} />
      <BulkToolbar
        selected={[...selected]}
        total={data?.total ?? 0}
        filter={filter}
        onClear={() => setSelected(new Set())}
        onDone={() => {
          setSelected(new Set());
          void mutate();
        }}
      />
      {error ? (
        <BackendAlert error={error} />
      ) : isLoading && !data ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : data && data.items.length === 0 ? (
        <Empty className="rounded-xl ring-1 ring-foreground/10">
          <EmptyHeader>
            <EmptyTitle>Nobody found</EmptyTitle>
            <EmptyDescription>Loosen the filter or run a sync from the Overview page.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : data ? (
        <>
          <PeopleTable
            people={data.items}
            selected={selected}
            onToggle={toggle}
            onToggleAll={toggleAll}
            sort={filter.sort}
            onSort={(sort) => setFilter({ ...filter, sort, page: 1 })}
          />
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span className="tabular-nums">
              Page {page} of {pages}
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setFilter({ ...filter, page: page - 1 })}>
                Previous
              </Button>
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setFilter({ ...filter, page: page + 1 })}>
                Next
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
