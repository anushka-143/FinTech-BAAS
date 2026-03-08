import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Send, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { aiAPI } from "@/lib/api";

interface Investigation {
  id: string;
  type: string;
  ref: string;
  summary: string;
  confidence: number;
  rootCause: string;
  action: string;
  model: string;
  latency: string;
  status: string;
  citations?: { source: string; title: string }[];
}

const investigations: Investigation[] = [
  {
    id: "AI-042",
    type: "PAYOUT_TRIAGE",
    ref: "PO-2026-00844",
    summary: "NEFT payout to BlueStar Ltd failed with provider error BENE_INACTIVE. Beneficiary account was marked dormant 3 days ago at the receiving bank. Recommend verifying beneficiary status and retrying via IMPS rail.",
    confidence: 92,
    rootCause: "Beneficiary account dormant at receiving bank",
    action: "Retry via IMPS after re-verification",
    model: "gemini-2.5-pro",
    latency: "2.1s",
    status: "COMPLETED",
  },
  {
    id: "AI-041",
    type: "RECON_INVESTIGATION",
    ref: "BRK-221",
    summary: "₹450 mismatch between internal payout record (₹4,52,000) and provider settlement (₹4,51,550). Provider statement shows ₹450 deducted as inter-bank processing charge. Recommend classifying as fee pass-through journal entry.",
    confidence: 88,
    rootCause: "Provider inter-bank processing fee",
    action: "Auto-classify as fee journal entry",
    model: "gemini-2.5-pro",
    latency: "3.4s",
    status: "COMPLETED",
  },
  {
    id: "AI-040",
    type: "KYC_REVIEW",
    ref: "KYC-4821",
    summary: "Meridian Finserv KYB: GST certificate shows director name mismatch (Suresh K. vs Suresh Kumar). PAN-Aadhaar cross-check passed. Likely abbreviation — not indicative of fraud.",
    confidence: 74,
    rootCause: "Name abbreviation in GST certificate",
    action: "Flag for manual ops confirmation",
    model: "gemini-2.5-pro",
    latency: "4.8s",
    status: "PENDING_ACTION",
    citations: [
      { source: "RBI KYC Master Direction 2016", title: "Section 8.2 — Name Variations" },
      { source: "PMLA Rules 2005", title: "Rule 9 — Customer Due Diligence" },
    ],
  },
];

export default function AICopilot() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const handleQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    toast.info("AI investigation started", {
      description: `Analyzing: "${query.slice(0, 60)}…"`,
      icon: <Sparkles className="w-4 h-4" />,
    });

    try {
      const response = await aiAPI.copilotAsk(query);
      toast.success("AI analysis complete", {
        description: `Confidence: ${Math.round((response.data?.confidence || 0) * 100)}% · ${response.data?.tools_used?.length || 0} tools used`,
      });
    } catch {
      toast.success("Investigation complete", {
        description: "Results displayed below (mock mode — API not connected)",
      });
    }
    setLoading(false);
    setQuery("");
  };

  return (
    <DashboardLayout title="AI Copilot" subtitle="Gemini-powered triage, investigation, and compliance Q&A">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <MetricCard label="Investigations today" value="18" changeType="neutral" />
        <MetricCard label="Avg confidence" value="86%" change="+2% vs last week" changeType="positive" />
        <MetricCard label="Avg latency" value="3.2s" change="gemini-2.5-pro reasoning" changeType="neutral" />
        <MetricCard label="Actions accepted" value="72%" change="By ops team this week" changeType="positive" />
      </div>

      {/* Query interface */}
      <div className="rounded-lg border border-border bg-card shadow-card p-4 md:p-5 mb-6">
        <div className="flex gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            placeholder="e.g. Why did PO-2026-00844 fail? / Investigate recon break BRK-221 / What are RBI KYC requirements for NBFCs?"
            className="flex-1 bg-accent border border-border rounded-lg px-4 py-2.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30 transition-shadow"
            disabled={loading}
          />
          <Button size="sm" className="h-auto px-4" onClick={handleQuery} disabled={loading}>
            {loading ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {["Payout Triage", "Recon Break", "KYC Review", "Compliance Q&A", "Risk Explain"].map((t) => (
            <button
              key={t}
              onClick={() => { setQuery(`Investigate ${t.toLowerCase()}`); toast.info(`${t} mode selected`); }}
              className="text-[11px] text-muted-foreground bg-accent border border-border hover:bg-accent/80 hover:text-foreground px-2.5 py-1 rounded-md transition-colors"
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Investigation results */}
      <div className="space-y-4 md:space-y-5">
        {investigations.map((inv) => (
          <div key={inv.id} className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between px-4 md:px-5 py-3.5 border-b border-border bg-accent/20 gap-2">
              <div className="flex items-center gap-2.5">
                <StatusBadge status={inv.status} variant={inv.status === "COMPLETED" ? "success" : "warning"} />
                <span className="font-mono text-[11px] text-muted-foreground">{inv.type}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 md:gap-4 text-[11px] text-muted-foreground font-mono">
                <span>ref:{inv.ref}</span>
                <span className="text-primary/70">{inv.model}</span>
                <span>{inv.latency}</span>
                <span>{inv.id}</span>
              </div>
            </div>
            <div className="px-4 md:px-5 py-4 md:py-5">
              <p className="text-[13px] text-foreground leading-relaxed mb-4 md:mb-5">{inv.summary}</p>

              {inv.citations && inv.citations.length > 0 && (
                <div className="mb-4 p-3 rounded-md bg-primary/5 border border-primary/10">
                  <p className="text-[10px] text-primary/70 uppercase tracking-[0.04em] font-medium mb-1.5">Sources</p>
                  {inv.citations.map((c, i) => (
                    <p key={i} className="text-[12px] text-muted-foreground">
                      <span className="text-primary/60 font-mono">[{i + 1}]</span> {c.source} — {c.title}
                    </p>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-5 pt-4 border-t border-border/50">
                <div>
                  <p className="text-[11px] text-muted-foreground uppercase tracking-[0.04em] mb-1.5 font-medium">Root Cause</p>
                  <p className="text-[13px] text-foreground">{inv.rootCause}</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground uppercase tracking-[0.04em] mb-1.5 font-medium">Recommended Action</p>
                  <p className="text-[13px] text-foreground">{inv.action}</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground uppercase tracking-[0.04em] mb-1.5 font-medium">Confidence</p>
                  <div className="flex items-center gap-2.5 mt-1">
                    <div className="flex-1 h-1.5 bg-accent rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-primary/60" style={{ width: `${inv.confidence}%` }} />
                    </div>
                    <span className="font-mono text-[13px] text-foreground tabular">{inv.confidence}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
