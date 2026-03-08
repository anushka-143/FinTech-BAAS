import { forwardRef } from "react";

interface StatusBadgeProps {
  status: string;
  variant?: "success" | "warning" | "destructive" | "info" | "default";
}

const styles: Record<string, string> = {
  success: "bg-success/8 text-success border-success/20",
  warning: "bg-warning/8 text-warning border-warning/20",
  destructive: "bg-destructive/8 text-destructive border-destructive/20",
  info: "bg-info/8 text-info border-info/20",
  default: "bg-muted text-muted-foreground border-border",
};

const StatusBadge = forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ status, variant = "default" }, ref) => {
    return (
      <span
        ref={ref}
        className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-[3px] rounded-md border ${styles[variant]}`}
      >
        {status}
      </span>
    );
  }
);

StatusBadge.displayName = "StatusBadge";

export default StatusBadge;
