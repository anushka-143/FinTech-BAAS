import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import AdvancedTable, { ColumnDef, FilterDef, SavedView } from "@/components/AdvancedTable";
import { NewCaseDialog } from "@/components/ActionDialogs";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { Plus } from "lucide-react";
import { kycAPI } from "@/lib/api";

interface KYCCase {
  id: string; entity: string; type: string; status: string; docs: number;
  confidence: number; assignee: string; created: string;
}

const MOCK_CASES: KYCCase[] = [
  { id: "KYC-4821", entity: "Meridian Finserv Pvt Ltd", type: "KYB", status: "IN_REVIEW", docs: 4, confidence: 87, assignee: "Ops Team", created: "Mar 7, 12:30" },
  { id: "KYC-4820", entity: "Priya Sharma", type: "KYC", status: "APPROVED", docs: 2, confidence: 96, assignee: "Auto", created: "Mar 7, 11:45" },
  { id: "KYC-4819", entity: "Delta Trading Co", type: "KYB", status: "PENDING_OCR", docs: 3, confidence: 0, assignee: "OCR Queue", created: "Mar 7, 11:20" },
  { id: "KYC-4818", entity: "Rajesh Patel", type: "KYC", status: "REJECTED", docs: 2, confidence: 42, assignee: "Risk Team", created: "Mar 7, 10:55" },
  { id: "KYC-4817", entity: "Bluewave Payments", type: "KYB", status: "APPROVED", docs: 5, confidence: 94, assignee: "Auto", created: "Mar 7, 10:10" },
  { id: "KYC-4816", entity: "Sunita Verma", type: "KYC", status: "SANCTIONS_HIT", docs: 2, confidence: 78, assignee: "Compliance", created: "Mar 7, 09:30" },
  { id: "KYC-4815", entity: "Apex Industries", type: "KYB", status: "IN_REVIEW", docs: 6, confidence: 82, assignee: "Ops Team", created: "Mar 7, 08:15" },
  { id: "KYC-4814", entity: "Mohan Kumar", type: "KYC", status: "APPROVED", docs: 2, confidence: 98, assignee: "Auto", created: "Mar 6, 17:30" },
];

const sv = (s: string) => {
  if (s === "APPROVED") return "success" as const;
  if (s === "PENDING_OCR" || s === "IN_REVIEW") return "warning" as const;
  if (s === "REJECTED" || s === "SANCTIONS_HIT") return "destructive" as const;
  return "default" as const;
};

const columns: ColumnDef<KYCCase>[] = [
  { key: "entity", label: "Entity", sortable: true, render: r => <span className="text-[13px] text-foreground font-medium">{r.entity}</span> },
  { key: "type", label: "Type", align: "center", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.type}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={sv(r.status)} /> },
  { key: "docs", label: "Docs", align: "center", render: r => <span className="text-[13px] text-muted-foreground">{r.docs}</span> },
  {
    key: "confidence", label: "Confidence", align: "center", sortable: true, render: r => (
      r.confidence > 0 ? (
        <span className={`font-mono text-[12px] ${r.confidence >= 90 ? "text-success" : r.confidence >= 70 ? "text-warning" : "text-destructive"}`}>{r.confidence}%</span>
      ) : <span className="text-muted-foreground">—</span>
    )
  },
  { key: "assignee", label: "Assignee", render: r => <span className="text-[12px] text-muted-foreground">{r.assignee}</span> },
  { key: "created", label: "Created", align: "right", sortable: true, render: r => <span className="text-[12px] text-muted-foreground">{r.created}</span> },
  { key: "id", label: "Case", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

const filters: FilterDef[] = [
  {
    key: "status", label: "Status", options: [
      { value: "APPROVED", label: "Approved" }, { value: "IN_REVIEW", label: "In review" },
      { value: "PENDING_OCR", label: "Pending OCR" }, { value: "REJECTED", label: "Rejected" },
      { value: "SANCTIONS_HIT", label: "Sanctions hit" },
    ]
  },
  {
    key: "type", label: "Type", options: [
      { value: "KYC", label: "KYC" }, { value: "KYB", label: "KYB" },
    ]
  },
];

const savedViews: SavedView[] = [
  { id: "review", name: "Pending review", filters: { status: "IN_REVIEW" } },
  { id: "sanctions", name: "Sanctions hits", filters: { status: "SANCTIONS_HIT" } },
  { id: "kyb-pending", name: "KYB pending > 24h", filters: { type: "KYB", status: "IN_REVIEW" } },
];

export default function KYC() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [newCaseOpen, setNewCaseOpen] = useState(false);
  const [cases, setCases] = useState<KYCCase[]>(MOCK_CASES);

  useEffect(() => {
    kycAPI.list().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setCases(res.data as KYCCase[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout
      title="KYC / KYB"
      subtitle="Verification, document AI, and compliance decisioning"
      actions={
        hasPermission("canApproveKYC") ? (
          <Button size="sm" className="h-8 text-[12px] px-3" onClick={() => setNewCaseOpen(true)}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />New Case
          </Button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Open cases" value="37" change="12 pending OCR review" changeType="neutral" />
        <MetricCard label="Auto-approved" value="68%" change="+4% this week" changeType="positive" />
        <MetricCard label="Avg OCR time" value="1.8s" change="PP-StructureV3 pipeline" changeType="neutral" />
        <MetricCard label="Sanctions hits" value="2" change="1 pending compliance review" changeType="destructive" />
      </div>

      <AdvancedTable
        data={cases}
        columns={columns}
        filters={filters}
        savedViews={savedViews}
        searchPlaceholder="Search cases…"
        getRowId={r => r.id}
        onRowClick={r => navigate(`/kyc/${r.id}`)}
        exportFileName="kyc-cases"
      />

      <NewCaseDialog open={newCaseOpen} onClose={() => setNewCaseOpen(false)} />
    </DashboardLayout>
  );
}
