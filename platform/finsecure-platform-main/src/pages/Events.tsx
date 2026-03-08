import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import StatusBadge from "@/components/StatusBadge";
import MetricCard from "@/components/MetricCard";
import AdvancedTable, { ColumnDef, FilterDef } from "@/components/AdvancedTable";
import { auditAPI } from "@/lib/api";

interface EventRow {
  id: string; topic: string; key: string; tenant: string; status: string; partition: number; time: string;
}

const MOCK_EVENTS: EventRow[] = [
  { id: "EVT-44821", topic: "payout.finalized", key: "PO-2026-00847", tenant: "T-ACME", status: "PROCESSED", partition: 2, time: "14:05:02.481" },
  { id: "EVT-44820", topic: "collection.received", key: "COL-88421", tenant: "T-ACME", status: "PROCESSED", partition: 0, time: "14:05:01.102" },
  { id: "EVT-44819", topic: "ledger.journal.posted", key: "JRN-0042", tenant: "T-ACME", status: "PROCESSED", partition: 1, time: "14:05:01.055" },
  { id: "EVT-44818", topic: "risk.alert.created", key: "RSK-1204", tenant: "T-ACME", status: "PROCESSED", partition: 3, time: "14:04:58.221" },
  { id: "EVT-44817", topic: "payout.callback.received", key: "PO-2026-00847", tenant: "T-ACME", status: "PROCESSED", partition: 2, time: "14:04:55.890" },
  { id: "EVT-44816", topic: "kyc.case.parsed", key: "KYC-4821", tenant: "T-MERIDIAN", status: "RETRY", partition: 0, time: "14:04:42.110" },
  { id: "EVT-44815", topic: "payout.sent", key: "PO-2026-00847", tenant: "T-ACME", status: "PROCESSED", partition: 2, time: "14:02:00.332" },
  { id: "EVT-44814", topic: "recon.break.detected", key: "BRK-221", tenant: "T-ACME", status: "PROCESSED", partition: 1, time: "14:01:55.005" },
];

const columns: ColumnDef<EventRow>[] = [
  { key: "topic", label: "Topic", sortable: true, render: r => <span className="font-mono text-[12px] text-foreground">{r.topic}</span> },
  { key: "key", label: "Key", render: r => <span className="font-mono text-[12px] text-muted-foreground">{r.key}</span> },
  { key: "tenant", label: "Tenant", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.tenant}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "PROCESSED" ? "success" : "warning"} /> },
  { key: "partition", label: "P", align: "center", render: r => <span className="font-mono text-[12px] text-muted-foreground">{r.partition}</span> },
  { key: "time", label: "Timestamp", align: "right", sortable: true, render: r => <span className="font-mono text-[12px] text-muted-foreground">{r.time}</span> },
  { key: "id", label: "Event", render: r => <span className="font-mono text-[10px] text-muted-foreground">{r.id}</span> },
];

const filters: FilterDef[] = [
  {
    key: "status", label: "Status", options: [
      { value: "PROCESSED", label: "Processed" }, { value: "RETRY", label: "Retry" },
    ]
  },
];

export default function Events() {
  const [events, setEvents] = useState<EventRow[]>(MOCK_EVENTS);

  useEffect(() => {
    auditAPI.list().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setEvents(res.data as EventRow[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout title="Event Stream" subtitle="Redpanda event bus — real-time log">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Events / min" value="847" change="Healthy throughput" changeType="neutral" />
        <MetricCard label="Active topics" value="14" change="4 partitions each" changeType="neutral" />
        <MetricCard label="Consumer lag" value="12" change="Within SLO target" changeType="neutral" />
        <MetricCard label="Retry queue" value="1" change="kyc.case.parsed" changeType="warning" />
      </div>

      <AdvancedTable
        data={events}
        columns={columns}
        filters={filters}
        searchPlaceholder="Search events…"
        getRowId={r => r.id}
        exportFileName="events"
      />
    </DashboardLayout>
  );
}
