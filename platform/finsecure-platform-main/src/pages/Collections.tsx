import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import AdvancedTable, { ColumnDef, FilterDef } from "@/components/AdvancedTable";
import { CreateVADialog } from "@/components/ActionDialogs";
import { CollectionsAIPanel } from "@/components/AIFeaturePanels";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { collectionsAPI } from "@/lib/api";

interface VA {
  id: string; name: string; ifsc: string; accountNo: string; balance: string; status: string; txnToday: number;
}
interface Collection {
  id: string; va: string; payer: string; amount: string; mode: string; status: string; time: string;
}

const MOCK_ACCOUNTS: VA[] = [
  { id: "VA-9001", name: "Acme Corp Collections", ifsc: "HDFC0001234", accountNo: "9201XXXX4821", balance: "₹18,42,000", status: "ACTIVE", txnToday: 24 },
  { id: "VA-9002", name: "Zenith Escrow", ifsc: "ICIC0005678", accountNo: "9201XXXX7732", balance: "₹5,60,000", status: "ACTIVE", txnToday: 8 },
  { id: "VA-9003", name: "Delta Nodal", ifsc: "SBIN0009012", accountNo: "9201XXXX1190", balance: "₹0", status: "FROZEN", txnToday: 0 },
  { id: "VA-9004", name: "QuickPay Settlements", ifsc: "UTIB0003456", accountNo: "9201XXXX3301", balance: "₹42,15,000", status: "ACTIVE", txnToday: 56 },
];

const MOCK_COLLECTIONS: Collection[] = [
  { id: "COL-88421", va: "VA-9001", payer: "INV-2026-1847", amount: "₹2,50,000", mode: "UPI", status: "SETTLED", time: "14:05" },
  { id: "COL-88420", va: "VA-9004", payer: "INV-2026-1846", amount: "₹8,90,000", mode: "NEFT", status: "PENDING_RECON", time: "13:52" },
  { id: "COL-88419", va: "VA-9001", payer: "INV-2026-1845", amount: "₹1,20,000", mode: "UPI", status: "SETTLED", time: "13:40" },
  { id: "COL-88418", va: "VA-9002", payer: "INV-2026-1844", amount: "₹5,60,000", mode: "RTGS", status: "SETTLED", time: "13:15" },
];

const vaColumns: ColumnDef<VA>[] = [
  { key: "name", label: "Name", sortable: true, render: r => <span className="text-[13px] text-foreground font-medium">{r.name}</span> },
  { key: "account", label: "Account", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.ifsc} · {r.accountNo}</span> },
  { key: "balance", label: "Balance", align: "right", sortable: true, render: r => <span className="font-mono text-[13px] text-foreground tabular">{r.balance}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "ACTIVE" ? "success" : "warning"} /> },
  { key: "txn", label: "Txn", align: "center", render: r => <span className="text-[13px] text-muted-foreground">{r.txnToday}</span> },
  { key: "id", label: "VA", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

const colColumns: ColumnDef<Collection>[] = [
  { key: "payer", label: "Payer ref", render: r => <span className="font-mono text-[12px] text-foreground">{r.payer}</span> },
  { key: "va", label: "VA", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.va}</span> },
  { key: "amount", label: "Amount", align: "right", sortable: true, render: r => <span className="font-mono text-[13px] text-foreground tabular">{r.amount}</span> },
  { key: "mode", label: "Mode", align: "center", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.mode}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "SETTLED" ? "success" : "warning"} /> },
  { key: "time", label: "Time", align: "right", render: r => <span className="text-[12px] text-muted-foreground">{r.time}</span> },
  { key: "id", label: "Txn", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

export default function Collections() {
  const { hasPermission } = useAuth();
  const [createVAOpen, setCreateVAOpen] = useState(false);
  const [accounts, setAccounts] = useState<VA[]>(MOCK_ACCOUNTS);
  const [collections, setCollections] = useState<Collection[]>(MOCK_COLLECTIONS);

  useEffect(() => {
    collectionsAPI.list().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setAccounts(res.data as VA[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout
      title="Virtual Accounts & Collections"
      subtitle="Inbound payment management and reconciliation"
      actions={
        hasPermission("canViewCollections") ? (
          <Button size="sm" className="h-8 text-[12px] px-3" onClick={() => setCreateVAOpen(true)}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />Create VA
          </Button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Active VAs" value="12" changeType="neutral" />
        <MetricCard label="Collections today" value="₹1.8Cr" change="+6.4% vs yesterday" changeType="positive" />
        <MetricCard label="Pending recon" value="3" change="₹12.4L unmatched" changeType="warning" />
        <MetricCard label="Avg settlement" value="< 2m" change="UPI/IMPS path" changeType="neutral" />
      </div>

      {/* AI Collections Intelligence */}
      <div className="mb-6">
        <CollectionsAIPanel />
      </div>

      <div className="mb-6">
        <h3 className="text-section text-foreground mb-3">Virtual accounts</h3>
        <AdvancedTable data={accounts} columns={vaColumns} searchPlaceholder="Search accounts…" getRowId={r => r.id} exportFileName="virtual-accounts" />
      </div>

      <div>
        <h3 className="text-section text-foreground mb-3">Recent collections</h3>
        <AdvancedTable data={collections} columns={colColumns} searchPlaceholder="Search collections…" getRowId={r => r.id} exportFileName="collections" />
      </div>

      <CreateVADialog open={createVAOpen} onClose={() => setCreateVAOpen(false)} />
    </DashboardLayout>
  );
}
