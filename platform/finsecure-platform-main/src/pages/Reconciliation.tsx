import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import AdvancedTable, { ColumnDef } from "@/components/AdvancedTable";
import { RunReconDialog } from "@/components/ActionDialogs";
import { ReconAIPanel } from "@/components/AIFeaturePanels";
import { Button } from "@/components/ui/button";
import { Play } from "lucide-react";
import { reconAPI } from "@/lib/api";

interface ReconRun {
  id: string; type: string; matched: number; breaks: number; autoResolved: number; status: string; time: string;
}

interface ReconBreak {
  id: string; type: string; internal: string; provider: string; diff: string; status: string; suggestion: string;
}

const MOCK_RUNS: ReconRun[] = [
  { id: "REC-0047", type: "PAYOUT_SETTLEMENT", matched: 142, breaks: 2, autoResolved: 1, status: "COMPLETED", time: "14:00" },
  { id: "REC-0046", type: "COLLECTION_INBOUND", matched: 89, breaks: 1, autoResolved: 1, status: "COMPLETED", time: "13:00" },
  { id: "REC-0045", type: "PAYOUT_SETTLEMENT", matched: 156, breaks: 4, autoResolved: 2, status: "BREAKS_OPEN", time: "12:00" },
  { id: "REC-0044", type: "VA_STATEMENT", matched: 67, breaks: 0, autoResolved: 0, status: "COMPLETED", time: "11:00" },
];

const MOCK_BREAKS: ReconBreak[] = [
  { id: "BRK-221", type: "AMOUNT_MISMATCH", internal: "₹4,52,000", provider: "₹4,51,550", diff: "₹450", status: "AI_TRIAGED", suggestion: "Fee deduction by provider" },
  { id: "BRK-220", type: "MISSING_PROVIDER", internal: "PO-2026-00841", provider: "—", diff: "₹3,80,000", status: "OPEN", suggestion: "Reversal not reflected yet" },
  { id: "BRK-219", type: "DUPLICATE_ENTRY", internal: "COL-88420", provider: "2× entries", diff: "₹8,90,000", status: "AUTO_RESOLVED", suggestion: "Duplicate callback deduplicated" },
];

const runColumns: ColumnDef<ReconRun>[] = [
  { key: "type", label: "Type", render: r => <span className="font-mono text-[12px] text-muted-foreground">{r.type}</span> },
  { key: "matched", label: "Matched", align: "center", sortable: true, render: r => <span className="text-[13px] text-foreground tabular">{r.matched}</span> },
  { key: "breaks", label: "Breaks", align: "center", render: r => <span className="text-[13px] text-foreground tabular">{r.breaks}</span> },
  { key: "auto", label: "Auto", align: "center", render: r => <span className="text-[13px] text-success tabular">{r.autoResolved}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "COMPLETED" ? "success" : "warning"} /> },
  { key: "time", label: "Time", align: "right", render: r => <span className="text-[12px] text-muted-foreground">{r.time}</span> },
  { key: "id", label: "Run", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

const breakColumns: ColumnDef<ReconBreak>[] = [
  { key: "type", label: "Type", render: r => <span className="font-mono text-[12px] text-muted-foreground">{r.type.replace("_", " ")}</span> },
  { key: "internal", label: "Internal", render: r => <span className="font-mono text-[12px] text-foreground">{r.internal}</span> },
  { key: "provider", label: "Provider", render: r => <span className="font-mono text-[12px] text-foreground">{r.provider}</span> },
  { key: "diff", label: "Difference", align: "right", render: r => <span className="font-mono text-[12px] text-destructive tabular">{r.diff}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "AUTO_RESOLVED" ? "success" : r.status === "AI_TRIAGED" ? "info" : "warning"} /> },
  { key: "suggestion", label: "AI suggestion", render: r => <span className="text-[12px] text-info truncate max-w-[200px] inline-block">{r.suggestion}</span> },
  { key: "id", label: "Break", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

export default function Reconciliation() {
  const navigate = useNavigate();
  const [runReconOpen, setRunReconOpen] = useState(false);
  const [runs, setRuns] = useState<ReconRun[]>(MOCK_RUNS);
  const [breaks, setBreaks] = useState<ReconBreak[]>(MOCK_BREAKS);

  useEffect(() => {
    reconAPI.runs().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setRuns(res.data as ReconRun[]);
    }).catch(() => { });
    reconAPI.breaks().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setBreaks(res.data as ReconBreak[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout
      title="Reconciliation"
      subtitle="Match internal transactions with provider statements"
      actions={
        <Button size="sm" className="h-8 text-[12px] px-3" onClick={() => setRunReconOpen(true)}>
          <Play className="w-3.5 h-3.5 mr-1.5" />Run Recon
        </Button>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Runs today" value="4" changeType="neutral" />
        <MetricCard label="Match rate" value="98.4%" change="+0.2% vs last week" changeType="positive" />
        <MetricCard label="Open breaks" value="3" change="1 AI-triaged" changeType="warning" />
        <MetricCard label="Auto-resolved" value="4" change="Today" changeType="positive" />
      </div>

      {/* AI Recon Intelligence */}
      <div className="mb-6">
        <ReconAIPanel />
      </div>

      <div className="mb-6">
        <h3 className="text-section text-foreground mb-3">Reconciliation runs</h3>
        <AdvancedTable
          data={runs}
          columns={runColumns}
          searchPlaceholder="Search runs…"
          getRowId={r => r.id}
          exportFileName="recon-runs"
        />
      </div>

      <div>
        <h3 className="text-section text-foreground mb-3">Breaks</h3>
        <AdvancedTable
          data={breaks}
          columns={breakColumns}
          searchPlaceholder="Search breaks…"
          getRowId={r => r.id}
          onRowClick={r => navigate(`/reconciliation/${r.id}`)}
          exportFileName="recon-breaks"
        />
      </div>

      <RunReconDialog open={runReconOpen} onClose={() => setRunReconOpen(false)} />
    </DashboardLayout>
  );
}
