import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import AdvancedTable, { ColumnDef, FilterDef } from "@/components/AdvancedTable";
import { ExplainableRiskPanel } from "@/components/AIFeaturePanels";
import { riskAPI } from "@/lib/api";

interface RiskAlert {
  id: string; type: string; entity: string; description: string; severity: string; status: string; time: string;
}

const MOCK_ALERTS: RiskAlert[] = [
  { id: "RSK-1204", type: "VELOCITY", entity: "Acme Corp", description: "15 payouts in 5 min exceeds threshold (10/5min)", severity: "HIGH", status: "OPEN", time: "14:08" },
  { id: "RSK-1203", type: "SANCTIONS", entity: "Sunita Verma", description: "Partial name match on OFAC SDN list (score: 78%)", severity: "CRITICAL", status: "INVESTIGATING", time: "13:45" },
  { id: "RSK-1202", type: "ANOMALY", entity: "QuickPay Inc", description: "Payout amount 4.2x above 30-day avg", severity: "MEDIUM", status: "RESOLVED", time: "12:30" },
  { id: "RSK-1201", type: "GRAPH_LINK", entity: "BlueStar ↔ Nova", description: "Shared beneficiary account across 2 tenants", severity: "HIGH", status: "OPEN", time: "11:15" },
  { id: "RSK-1200", type: "RULE_HIT", entity: "Delta Trading", description: "PEP association detected in KYB documents", severity: "HIGH", status: "ESCALATED", time: "10:40" },
];

const sev = (s: string) => {
  if (s === "CRITICAL") return "destructive" as const;
  if (s === "HIGH") return "warning" as const;
  if (s === "MEDIUM") return "info" as const;
  return "default" as const;
};

const stat = (s: string) => {
  if (s === "RESOLVED") return "success" as const;
  if (s === "OPEN") return "warning" as const;
  if (s === "INVESTIGATING" || s === "ESCALATED") return "info" as const;
  return "default" as const;
};

const columns: ColumnDef<RiskAlert>[] = [
  { key: "entity", label: "Entity", sortable: true, render: r => <span className="text-[13px] text-foreground font-medium">{r.entity}</span> },
  { key: "type", label: "Type", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.type}</span> },
  { key: "description", label: "Description", render: r => <span className="text-[12px] text-muted-foreground max-w-[300px] truncate inline-block">{r.description}</span> },
  { key: "severity", label: "Severity", render: r => <StatusBadge status={r.severity} variant={sev(r.severity)} /> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={stat(r.status)} /> },
  { key: "time", label: "Time", align: "right", sortable: true, render: r => <span className="text-[12px] text-muted-foreground">{r.time}</span> },
  { key: "id", label: "Alert", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

const filters: FilterDef[] = [
  {
    key: "severity", label: "Severity", options: [
      { value: "CRITICAL", label: "Critical" }, { value: "HIGH", label: "High" }, { value: "MEDIUM", label: "Medium" },
    ]
  },
  {
    key: "status", label: "Status", options: [
      { value: "OPEN", label: "Open" }, { value: "INVESTIGATING", label: "Investigating" },
      { value: "ESCALATED", label: "Escalated" }, { value: "RESOLVED", label: "Resolved" },
    ]
  },
];

export default function Risk() {
  const [alerts, setAlerts] = useState<RiskAlert[]>(MOCK_ALERTS);

  useEffect(() => {
    riskAPI.alerts().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setAlerts(res.data as RiskAlert[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout title="Risk & AML" subtitle="Rules engine, velocity checks, sanctions screening, anomaly detection">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Active alerts" value="8" change="3 critical severity" changeType="destructive" />
        <MetricCard label="Sanctions hits" value="2" change="1 pending compliance review" changeType="destructive" />
        <MetricCard label="Rules triggered" value="24" change="Today" changeType="neutral" />
        <MetricCard label="False positive rate" value="12%" change="-3% vs last month" changeType="positive" />
      </div>

      {/* AI Intelligence */}
      <div className="mb-6">
        <ExplainableRiskPanel />
      </div>

      <AdvancedTable
        data={alerts}
        columns={columns}
        filters={filters}
        searchPlaceholder="Search alerts…"
        getRowId={r => r.id}
        exportFileName="risk-alerts"
      />
    </DashboardLayout>
  );
}
