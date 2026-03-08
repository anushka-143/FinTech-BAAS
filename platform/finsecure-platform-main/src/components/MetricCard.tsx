interface MetricCardProps {
  label: string;
  value: string;
  change?: string;
  changeType?: "positive" | "negative" | "neutral" | "destructive" | "warning";
}

export default function MetricCard({ label, value, change, changeType = "neutral" }: MetricCardProps) {
  const changeColor = {
    positive: "text-success",
    negative: "text-destructive",
    neutral: "text-muted-foreground",
    destructive: "text-destructive",
    warning: "text-warning",
  }[changeType];

  return (
    <div className="rounded-lg border border-border bg-card px-5 py-5 shadow-card">
      <p className="text-label text-muted-foreground mb-3">{label}</p>
      <p className="text-kpi text-foreground tabular">{value}</p>
      {change && <p className={`text-meta mt-2 ${changeColor}`}>{change}</p>}
    </div>
  );
}
