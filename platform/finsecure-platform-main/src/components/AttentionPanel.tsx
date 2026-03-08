import { ReactNode } from "react";
import { toast } from "sonner";

interface AttentionItemProps {
  severity: "critical" | "warning" | "info";
  title: string;
  meta: string;
  action?: string;
  id: string;
  onAction?: () => void;
}

const severityStyles = {
  critical: "border-l-destructive/50",
  warning: "border-l-warning/50",
  info: "border-l-info/50",
};

const severityDot = {
  critical: "bg-destructive",
  warning: "bg-warning",
  info: "bg-info",
};

export function AttentionItem({ severity, title, meta, action, id, onAction }: AttentionItemProps) {
  const handleClick = () => {
    if (onAction) {
      onAction();
    } else if (action) {
      toast.info(`${action}: ${id}`, { description: title });
    }
  };

  return (
    <div
      className={`border-l-2 ${severityStyles[severity]} pl-3 py-2 group cursor-pointer hover:bg-accent/30 transition-colors rounded-r-md`}
      onClick={handleClick}
    >
      <div className="flex items-start gap-2">
        <span className={`w-[6px] h-[6px] rounded-full mt-[5px] shrink-0 ${severityDot[severity]}`} />
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-foreground leading-snug">{title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-mono text-muted-foreground">{id}</span>
            <span className="text-[10px] text-muted-foreground">·</span>
            <span className="text-[10px] text-muted-foreground">{meta}</span>
          </div>
          {action && (
            <p className="text-[10px] text-primary mt-1 font-medium opacity-0 group-hover:opacity-100 transition-opacity">{action} →</p>
          )}
        </div>
      </div>
    </div>
  );
}

interface AttentionPanelProps {
  title: string;
  children: ReactNode;
}

export function AttentionPanel({ title, children }: AttentionPanelProps) {
  return (
    <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <span className="text-section text-foreground">{title}</span>
      </div>
      <div className="p-3 space-y-1">
        {children}
      </div>
    </div>
  );
}
