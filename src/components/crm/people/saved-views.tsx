"use client";

import { useState } from "react";
import useSWR from "swr";
import { BookmarkIcon, ChevronDownIcon, TrashIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, fetcher } from "@/lib/crm/api";
import type { PeopleFilter, SavedViewOut } from "@/lib/crm/types";

export function SavedViews({ filter, onApply }: { filter: PeopleFilter; onApply: (f: PeopleFilter) => void }) {
  const { data, mutate } = useSWR<SavedViewOut[]>("/views", fetcher);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");

  const save = async () => {
    if (!name.trim()) return;
    const rest: PeopleFilter = { ...filter };
    delete rest.page;
    delete rest.page_size;
    try {
      await api.post("/views", { name: name.trim(), filter: rest });
      toast.success(`View “${name.trim()}” saved`);
      setOpen(false);
      setName("");
      void mutate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button size="sm" variant="outline" />}>
          <BookmarkIcon /> Views <ChevronDownIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-56">
          <DropdownMenuItem onClick={() => setOpen(true)}>Save current filter…</DropdownMenuItem>
          {data && data.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Saved views</DropdownMenuLabel>
              {data.map((v) => (
                <DropdownMenuItem key={v.id} onClick={() => onApply({ ...v.filter, page: 1 })} className="justify-between">
                  <span className="truncate">{v.name}</span>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    aria-label="Delete view"
                    onClick={async (e) => {
                      e.stopPropagation();
                      await api.del(`/views/${v.id}`);
                      void mutate();
                    }}
                  >
                    <TrashIcon />
                  </Button>
                </DropdownMenuItem>
              ))}
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save view</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
            className="space-y-3"
          >
            <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
            <DialogFooter>
              <Button type="submit" disabled={!name.trim()}>
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
