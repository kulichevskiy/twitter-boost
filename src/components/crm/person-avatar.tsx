import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { initials } from "@/lib/crm/format";
import { cn } from "cn";

export function PersonAvatar({
  src,
  name,
  handle,
  className,
}: {
  src?: string | null;
  name?: string | null;
  handle?: string | null;
  className?: string;
}) {
  return (
    <Avatar className={cn("size-8", className)}>
      {src ? <AvatarImage src={src} alt={handle ?? name ?? ""} /> : null}
      <AvatarFallback className="text-[10px]">{initials(name, handle)}</AvatarFallback>
    </Avatar>
  );
}
