import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import AdvancedTable, { ColumnDef, FilterDef, SavedView } from "@/components/AdvancedTable";
import { NewPayoutDialog } from "@/components/ActionDialogs";
import { SmartRoutingPanel, NameMatchPanel } from "@/components/AIFeaturePanels";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { payoutsAPI } from "@/lib/api";

interface Payout {
  id: string; beneficiary: string; account: string; amount: string; rail: string;
  status: string; initiated: string; settled: string;
}

const MOCK_PAYOUTS: Payout[] = [
  { id: "PO-2026-00847", beneficiary: "Acme Corp", account: "HDFC ****4821", amount: "₹4,52,000", rail: "IMPS", status: "SUCCESS", initiated: "Mar 7, 14:02", settled: "14:02" },
  { id: "PO-2026-00846", beneficiary: "Zenith Technologies", account: "ICICI ****7732", amount: "₹12,80,000", rail: "RTGS", status: "PENDING", initiated: "Mar 7, 13:58", settled: "—" },
  { id: "PO-2026-00845", beneficiary: "Nova Finance", account: "SBI ****1190", amount: "₹89,500", rail: "UPI", status: "SUCCESS", initiated: "Mar 7, 13:55", settled: "13:55" },
  { id: "PO-2026-00844", beneficiary: "BlueStar Ltd", account: "Axis ****3301", amount: "₹2,15,000", rail: "NEFT", status: "FAILED_RETRYABLE", initiated: "Mar 7, 13:50", settled: "—" },
  { id: "PO-2026-00843", beneficiary: "QuickPay Inc", account: "HDFC ****9087", amount: "₹1,45,000", rail: "UPI", status: "SUCCESS", initiated: "Mar 7, 13:44", settled: "13:44" },
  { id: "PO-2026-00842", beneficiary: "Greenfield Agri", account: "PNB ****5543", amount: "₹7,20,000", rail: "RTGS", status: "SUCCESS", initiated: "Mar 7, 13:30", settled: "13:31" },
  { id: "PO-2026-00841", beneficiary: "TechNova AI", account: "Kotak ****2218", amount: "₹3,80,000", rail: "IMPS", status: "REVERSED", initiated: "Mar 7, 13:15", settled: "13:22" },
  { id: "PO-2026-00840", beneficiary: "Pinnacle Corp", account: "BOB ****6612", amount: "₹5,40,000", rail: "NEFT", status: "SUCCESS", initiated: "Mar 7, 12:50", settled: "12:55" },
  { id: "PO-2026-00839", beneficiary: "Nexus Holdings", account: "HDFC ****3340", amount: "₹18,00,000", rail: "RTGS", status: "SUCCESS", initiated: "Mar 7, 12:30", settled: "12:31" },
  { id: "PO-2026-00838", beneficiary: "CloudSync Ltd", account: "SBI ****8870", amount: "₹67,000", rail: "UPI", status: "FAILED", initiated: "Mar 7, 12:10", settled: "—" },
  { id: "PO-2026-00837", beneficiary: "Bright Payments", account: "ICICI ****2209", amount: "₹2,90,000", rail: "IMPS", status: "SUCCESS", initiated: "Mar 7, 11:45", settled: "11:45" },
  { id: "PO-2026-00836", beneficiary: "Metro Logistics", account: "Axis ****4455", amount: "₹11,20,000", rail: "RTGS", status: "PENDING", initiated: "Mar 7, 11:20", settled: "—" },
];

const sv = (s: string) => {
  if (s === "SUCCESS") return "success" as const;
  if (s === "PENDING") return "warning" as const;
  if (s.includes("FAILED")) return "destructive" as const;
  if (s === "REVERSED") return "info" as const;
  return "default" as const;
};

const columns: ColumnDef<Payout>[] = [
  { key: "beneficiary", label: "Beneficiary", sortable: true, render: r => <span className="text-[13px] text-foreground font-medium">{r.beneficiary}</span> },
  { key: "account", label: "Account", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.account}</span> },
  { key: "amount", label: "Amount", align: "right", sortable: true, render: r => <span className="font-mono text-[13px] text-foreground tabular">{r.amount}</span> },
  { key: "rail", label: "Rail", align: "center", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.rail}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={sv(r.status)} /> },
  { key: "initiated", label: "Initiated", align: "right", sortable: true, render: r => <span className="text-[12px] text-muted-foreground">{r.initiated}</span> },
  { key: "settled", label: "Settled", align: "right", render: r => <span className="text-[12px] text-muted-foreground">{r.settled}</span> },
  { key: "id", label: "ID", defaultVisible: false, render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

const filters: FilterDef[] = [
  {
    key: "status", label: "Status", options: [
      { value: "SUCCESS", label: "Success" }, { value: "PENDING", label: "Pending" },
      { value: "FAILED", label: "Failed" }, { value: "REVERSED", label: "Reversed" },
    ]
  },
  {
    key: "rail", label: "Rail", options: [
      { value: "IMPS", label: "IMPS" }, { value: "NEFT", label: "NEFT" },
      { value: "RTGS", label: "RTGS" }, { value: "UPI", label: "UPI" },
    ]
  },
];

const savedViews: SavedView[] = [
  { id: "failed", name: "Failed payouts", filters: { status: "FAILED" } },
  { id: "pending", name: "Pending payouts", filters: { status: "PENDING" } },
  { id: "neft-failed", name: "Failed NEFT", filters: { status: "FAILED", rail: "NEFT" } },
];

export default function Payouts() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [newPayoutOpen, setNewPayoutOpen] = useState(false);
  const [payouts, setPayouts] = useState<Payout[]>(MOCK_PAYOUTS);

  useEffect(() => {
    payoutsAPI.list().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setPayouts(res.data as Payout[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout
      title="Payouts"
      subtitle="Initiation, routing, status, and settlement"
      actions={
        hasPermission("canCreatePayouts") ? (
          <Button size="sm" className="h-8 text-[12px] px-3" onClick={() => setNewPayoutOpen(true)}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />New Payout
          </Button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Volume today" value="₹32.9Cr" change="+12.5% vs yesterday" changeType="positive" />
        <MetricCard label="Success rate" value="94.2%" change="-0.8% vs yesterday" changeType="negative" />
        <MetricCard label="Avg settlement" value="18s" change="IMPS/UPI average" changeType="neutral" />
        <MetricCard label="Failed / retryable" value="6 / 2" change="4 require manual review" changeType="destructive" />
      </div>

      {/* AI Intelligence Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <SmartRoutingPanel />
        <NameMatchPanel />
      </div>

      <AdvancedTable
        data={payouts}
        columns={columns}
        filters={filters}
        savedViews={savedViews}
        searchPlaceholder="Search payouts…"
        getRowId={r => r.id}
        onRowClick={r => navigate(`/payouts/${r.id}`)}
        pageSize={10}
        exportFileName="payouts"
        bulkActions={hasPermission("canRetryPayouts") ? [
          { label: "Retry selected", action: (ids) => toast.success("Retry queued", { description: `${ids.length} payouts queued for retry.` }) },
        ] : []}
      />

      <NewPayoutDialog open={newPayoutOpen} onClose={() => setNewPayoutOpen(false)} />
    </DashboardLayout>
  );
}
