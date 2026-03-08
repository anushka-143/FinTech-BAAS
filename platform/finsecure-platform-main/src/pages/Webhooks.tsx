import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import StatusBadge from "@/components/StatusBadge";
import MetricCard from "@/components/MetricCard";
import AdvancedTable, { ColumnDef, FilterDef } from "@/components/AdvancedTable";
import { AddEndpointDialog } from "@/components/ActionDialogs";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { Plus } from "lucide-react";
import { webhooksAPI } from "@/lib/api";

interface Endpoint {
  id: string; url: string; events: string; status: string; successRate: string; lastDelivery: string;
}
interface Delivery {
  id: string; endpoint: string; event: string; status: string; attempts: number; latency: string; time: string;
}

const MOCK_ENDPOINTS: Endpoint[] = [
  { id: "WH-001", url: "https://api.acme.com/webhooks/finstack", events: "payout.*, collection.*", status: "ACTIVE", successRate: "99.2%", lastDelivery: "2s ago" },
  { id: "WH-002", url: "https://hooks.zenith.io/v1/payments", events: "payout.finalized", status: "ACTIVE", successRate: "97.8%", lastDelivery: "5m ago" },
  { id: "WH-003", url: "https://nova.finance/callbacks", events: "collection.*, recon.*", status: "FAILING", successRate: "42.1%", lastDelivery: "12m ago" },
];

const MOCK_DELIVERIES: Delivery[] = [
  { id: "DLV-99421", endpoint: "WH-001", event: "payout.finalized", status: "DELIVERED", attempts: 1, latency: "120ms", time: "14:05" },
  { id: "DLV-99420", endpoint: "WH-003", event: "collection.received", status: "FAILED_RETRY", attempts: 3, latency: "—", time: "14:02" },
  { id: "DLV-99419", endpoint: "WH-001", event: "collection.settled", status: "DELIVERED", attempts: 1, latency: "89ms", time: "13:58" },
  { id: "DLV-99418", endpoint: "WH-002", event: "payout.finalized", status: "DELIVERED", attempts: 1, latency: "205ms", time: "13:55" },
  { id: "DLV-99417", endpoint: "WH-003", event: "recon.break.detected", status: "DLQ", attempts: 5, latency: "—", time: "13:40" },
];

const epColumns: ColumnDef<Endpoint>[] = [
  { key: "url", label: "URL", render: r => <span className="text-[13px] text-foreground font-medium truncate max-w-[280px] inline-block">{r.url}</span> },
  { key: "events", label: "Events", render: r => <span className="font-mono text-[10px] text-muted-foreground">{r.events}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "ACTIVE" ? "success" : "destructive"} /> },
  { key: "successRate", label: "Success", align: "right", render: r => <span className="font-mono text-[12px] text-foreground tabular">{r.successRate}</span> },
  { key: "lastDelivery", label: "Last", align: "right", render: r => <span className="text-[12px] text-muted-foreground">{r.lastDelivery}</span> },
  { key: "id", label: "ID", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.id}</span> },
];

const dlvColumns: ColumnDef<Delivery>[] = [
  { key: "event", label: "Event", sortable: true, render: r => <span className="font-mono text-[12px] text-foreground">{r.event}</span> },
  { key: "endpoint", label: "Endpoint", render: r => <span className="font-mono text-[11px] text-muted-foreground">{r.endpoint}</span> },
  { key: "status", label: "Status", render: r => <StatusBadge status={r.status} variant={r.status === "DELIVERED" ? "success" : r.status === "DLQ" ? "destructive" : "warning"} /> },
  { key: "attempts", label: "Attempts", align: "center", render: r => <span className="text-[13px] text-muted-foreground tabular">{r.attempts}</span> },
  { key: "latency", label: "Latency", align: "center", render: r => <span className="font-mono text-[12px] text-muted-foreground">{r.latency}</span> },
  { key: "time", label: "Time", align: "right", render: r => <span className="text-[12px] text-muted-foreground">{r.time}</span> },
  { key: "id", label: "ID", render: r => <span className="font-mono text-[10px] text-muted-foreground">{r.id}</span> },
];

const dlvFilters: FilterDef[] = [
  {
    key: "status", label: "Status", options: [
      { value: "DELIVERED", label: "Delivered" }, { value: "FAILED_RETRY", label: "Failed" }, { value: "DLQ", label: "DLQ" },
    ]
  },
];

export default function Webhooks() {
  const { hasPermission } = useAuth();
  const [addEndpointOpen, setAddEndpointOpen] = useState(false);
  const [endpoints, setEndpoints] = useState<Endpoint[]>(MOCK_ENDPOINTS);
  const [deliveries] = useState<Delivery[]>(MOCK_DELIVERIES);

  useEffect(() => {
    webhooksAPI.list().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setEndpoints(res.data as Endpoint[]);
    }).catch(() => { });
  }, []);

  return (
    <DashboardLayout
      title="Webhooks"
      subtitle="Outbound delivery, endpoint health, and replay"
      actions={
        hasPermission("canManageWebhooks") ? (
          <Button size="sm" className="h-8 text-[12px] px-3" onClick={() => setAddEndpointOpen(true)}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />Add Endpoint
          </Button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Endpoints" value="3" changeType="neutral" />
        <MetricCard label="Deliveries today" value="847" changeType="neutral" />
        <MetricCard label="Success rate" value="94.8%" change="1 endpoint failing" changeType="warning" />
        <MetricCard label="DLQ items" value="3" change="Require manual replay" changeType="destructive" />
      </div>

      <div className="mb-6">
        <h3 className="text-section text-foreground mb-3">Webhook endpoints</h3>
        <AdvancedTable data={endpoints} columns={epColumns} searchPlaceholder="Search endpoints…" getRowId={r => r.id} />
      </div>

      <div>
        <h3 className="text-section text-foreground mb-3">Recent deliveries</h3>
        <AdvancedTable data={deliveries} columns={dlvColumns} filters={dlvFilters} searchPlaceholder="Search deliveries…" getRowId={r => r.id} exportFileName="webhook-deliveries" />
      </div>

      <AddEndpointDialog open={addEndpointOpen} onClose={() => setAddEndpointOpen(false)} />
    </DashboardLayout>
  );
}
