import { ReactNode } from "react";

interface TimelineEvent {
  id: string;
  time: string;
  title: string;
  description?: string;
  actor?: string;
  type?: "system" | "user" | "ai";
}

interface AuditTimelineProps {
  events: TimelineEvent[];
  title?: string;
}

const typeIndicators = {
  system: "bg-muted-foreground/40",
  user: "bg-primary",
  ai: "bg-info",
};

export default function AuditTimeline({ events, title = "Timeline" }: AuditTimelineProps) {
  return (
    <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <span className="text-section text-foreground">{title}</span>
      </div>
      <div className="px-5 py-4">
        <div className="relative">
          {events.map((event, i) => (
            <div key={event.id} className="flex gap-4 pb-5 last:pb-0">
              {/* Line + dot */}
              <div className="flex flex-col items-center shrink-0">
                <div className={`w-2.5 h-2.5 rounded-full mt-1 ${typeIndicators[event.type || "system"]}`} />
                {i < events.length - 1 && <div className="w-px flex-1 bg-border mt-1" />}
              </div>
              {/* Content */}
              <div className="flex-1 min-w-0 -mt-0.5">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-[13px] font-medium text-foreground">{event.title}</p>
                  <span className="text-[11px] text-muted-foreground shrink-0 font-mono">{event.time}</span>
                </div>
                {event.description && (
                  <p className="text-[12px] text-muted-foreground mt-0.5">{event.description}</p>
                )}
                {event.actor && (
                  <p className="text-[11px] text-muted-foreground/60 mt-0.5">by {event.actor}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export type { TimelineEvent };
