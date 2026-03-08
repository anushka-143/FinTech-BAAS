import { useLiveRefresh } from "@/hooks/use-live-time";

interface LiveIndicatorProps {
  intervalMs?: number;
}

export default function LiveIndicator({ intervalMs = 30000 }: LiveIndicatorProps) {
  const { refreshedAgo } = useLiveRefresh(intervalMs);

  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-success" />
      </span>
      <span>Live · {refreshedAgo()}</span>
    </div>
  );
}
