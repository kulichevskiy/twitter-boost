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
      toast.success(`Вид «${name.trim()}» сохранён`);
      setOpen(false);
      setName("");
      void mutate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button size="sm" variant="outline" />}>
          <BookmarkIcon /> Виды <ChevronDownIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-56">
          <DropdownMenuItem onClick={() => setOpen(true)}>Сохранить текущий фильтр…</DropdownMenuItem>
          {data && data.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Сохранённые</DropdownMenuLabel>
              {data.map((v) => (
                <DropdownMenuItem key={v.id} onClick={() => onApply({ ...v.filter, page: 1 })} className="justify-between">
                  <span className="truncate">{v.name}</span>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    aria-label="Удалить вид"
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
            <DialogTitle>Сохранить вид</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
            className="space-y-3"
          >
            <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Название" />
            <DialogFooter>
              <Button type="submit" disabled={!name.trim()}>
                Сохранить
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
