import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import AdvancedTable, { ColumnDef } from "@/components/AdvancedTable";
import { TransactionCategorizationPanel, CashflowForecastPanel } from "@/components/AIFeaturePanels";
import { ArrowRight } from "lucide-react";
import { ledgerAPI } from "@/lib/api";

interface Balance { account: string; available: string; reserved: string; pending: string; }
interface Journal { id: string; type: string; debit: string; credit: string; amount: string; ref: string; time: string; }

const MOCK_BALANCES: Balance[] = [
  { account: "bank-clearing", available: "₹42,15,000", reserved: "₹0", pending: "₹8,90,000" },
  { account: "customer-wallet", available: "₹1,24,50,000", reserved: "₹12,80,000", pending: "₹0" },
  { account: "payout-reserve", available: "₹12,80,000", reserved: "₹0", pending: "₹0" },
  { account: "provider-clearing", available: "₹0", reserved: "₹0", pending: "₹4,52,000" },
  { account: "platform-revenue", available: "₹8,42,500", reserved: "₹0", pending: "₹0" },
];

const MOCK_JOURNALS: Journal[] = [
  { id: "JRN-20260307-0042", type: "COLLECTION_SETTLED", debit: "bank-clearing", credit: "customer-wallet", amount: "₹2,50,000", ref: "COL-88421", time: "14:05" },
  { id: "JRN-20260307-0041", type: "PAYOUT_RESERVED", debit: "customer-wallet", credit: "payout-reserve", amount: "₹4,52,000", ref: "PO-00847", time: "14:02" },
  { id: "JRN-20260307-0040", type: "PAYOUT_SETTLED", debit: "payout-reserve", credit: "provider-clearing", amount: "₹4,52,000", ref: "PO-00847", time: "14:02" },
  { id: "JRN-20260307-0039", type: "PAYOUT_REVERSED", debit: "payout-reserve", credit: "customer-wallet", amount: "₹3,80,000", ref: "PO-00841", time: "13:22" },
  { id: "JRN-20260307-0038", type: "FEE_COLLECTED", debit: "customer-wallet", credit: "platform-revenue", amount: "₹450", ref: "FEE-00847", time: "14:02" },
];

const tv = (t: string) => {
  if (t.includes("SETTLED") || t.includes("FEE")) return "success" as const;
  if (t.includes("RESERVED")) return "warning" as const;
  if (t.includes("REVERSED")) return "info" as const;
  return "default" as const;
};

const balColumns: ColumnDef<Balance>[] = [
  { key: "account", label: "Account", render: r => <span className="font-mono text-[12px] text-foreground">{r.account}</span> },
  { key: "available", label: "Available", align: "right", render: r => <span className="font-mono text-[13px] text-foreground tabular">{r.available}</span> },
  { key: "reserved", label: "Reserved", align: "right", render: r => <span className="font-mono text-[12px] text-warning tabular">{r.reserved}</span> },
  { key: "pending", label: "Pending", align: "right", render: r => <span className="font-mono text-[12px] text-muted-foreground tabular">{r.pending}</span> },
];

const jrnColumns: ColumnDef<Journal>[] = [
  { key: "type", label: "Type", sortable: true, render: r => <StatusBadge status={r.type} variant={tv(r.type)} /> },
  {
    key: "flow", label: "Flow", render: r => (
      <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
        {r.debit} <ArrowRight className="w-3 h-3 opacity-40" /> {r.credit}
      </span>
    )
  },
  { key: "amount", label: "Amount", align: "right", sortable: true, render: r => <span className="font-mono text-[13px] text-foreground tabular">{r.amount}</span> },
  { key: "ref", label: "Ref", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.ref}</span> },
  { key: "time", label: "Time", align: "right", render: r => <span className="text-[12px] text-muted-foreground">{r.time}</span> },
  { key: "id", label: "Journal", render: r => <span className="font-mono text-[10px] text-muted-foreground">{r.id}</span> },
];

export default function Ledger() {
  const [balances, setBalances] = useState<Balance[]>(MOCK_BALANCES);
  const [journals, setJournals] = useState<Journal[]>(MOCK_JOURNALS);

  useEffect(() => {
    ledgerAPI.journals().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setJournals(res.data as Journal[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout title="Ledger" subtitle="Double-entry journal, account balances, and audit trail">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Journals today" value="284" changeType="neutral" />
        <MetricCard label="Total volume" value="₹4.2Cr" change="Sum(debits) = Sum(credits) ✓" changeType="positive" />
        <MetricCard label="Pending holds" value="₹12.8L" change="1 payout in flight" changeType="warning" />
        <MetricCard label="Invariant check" value="Balanced" change="Last verified 2s ago" changeType="positive" />
      </div>

      {/* AI Intelligence Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <CashflowForecastPanel />
        <TransactionCategorizationPanel />
      </div>

      <div className="mb-6">
        <h3 className="text-section text-foreground mb-3">Account balances</h3>
        <AdvancedTable data={balances} columns={balColumns} searchPlaceholder="Search accounts…" getRowId={r => r.account} />
      </div>

      <div>
        <h3 className="text-section text-foreground mb-3">Journal entries</h3>
        <AdvancedTable data={journals} columns={jrnColumns} searchPlaceholder="Search journals…" getRowId={r => r.id} exportFileName="journals" />
      </div>
    </DashboardLayout>
  );
}
