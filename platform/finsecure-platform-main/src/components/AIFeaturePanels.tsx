import { ReactNode, useState } from "react";
import { Cpu, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import StatusBadge from "@/components/StatusBadge";

/* ─── Shared AI Panel ─── */
interface AIPanelProps {
  title: string;
  confidence?: number;
  children: ReactNode;
  collapsible?: boolean;
  badge?: string;
}

export function AIPanel({ title, confidence, children, collapsible, badge }: AIPanelProps) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-lg border border-info/20 bg-info/[0.03] overflow-hidden">
      <button
        className="flex items-center gap-2 px-4 md:px-5 py-3 border-b border-info/10 w-full text-left"
        onClick={collapsible ? () => setOpen(!open) : undefined}
      >
        <Cpu className="w-4 h-4 text-info shrink-0" />
        <span className="text-[13px] font-medium text-info">{title}</span>
        {badge && <StatusBadge status={badge} variant="info" />}
        {confidence !== undefined && (
          <span className="font-mono text-[11px] text-info/60 ml-auto mr-2">{confidence}% confidence</span>
        )}
        {collapsible && (open ? <ChevronUp className="w-3.5 h-3.5 text-info/50" /> : <ChevronDown className="w-3.5 h-3.5 text-info/50" />)}
      </button>
      {open && <div className="px-4 md:px-5 py-4">{children}</div>}
    </div>
  );
}

/* ─── Smart Payout Routing ─── */
interface RoutingDecision {
  rail: string;
  score: number;
  reasons: string[];
  fallbacks: string[];
  costEstimate: string;
  speedEstimate: string;
}

const mockRouting: RoutingDecision = {
  rail: "IMPS",
  score: 94,
  reasons: ["Highest success rate for HDFC (99.2%)", "Amount ₹4.52L within IMPS cap (₹5L)", "Instant settlement — 4s avg"],
  fallbacks: ["NEFT (score: 82)", "RTGS (score: 71)"],
  costEstimate: "₹5.90",
  speedEstimate: "~4s",
};

export function SmartRoutingPanel({ amount, beneficiaryBank }: { amount?: string; beneficiaryBank?: string }) {
  return (
    <AIPanel title="Smart routing" confidence={mockRouting.score} badge="Auto-selected">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[14px] font-semibold text-foreground">{mockRouting.rail}</p>
            <p className="text-[12px] text-muted-foreground">Recommended rail</p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[13px] text-foreground tabular">{mockRouting.costEstimate}</p>
            <p className="text-[11px] text-muted-foreground">{mockRouting.speedEstimate} settlement</p>
          </div>
        </div>
        <div className="space-y-1.5">
          {mockRouting.reasons.map((r, i) => (
            <div key={i} className="flex items-start gap-2">
              <Sparkles className="w-3 h-3 text-info mt-0.5 shrink-0" />
              <span className="text-[12px] text-foreground leading-relaxed">{r}</span>
            </div>
          ))}
        </div>
        <div className="pt-3 border-t border-info/10">
          <p className="text-[11px] text-muted-foreground mb-1.5">Fallback chain</p>
          <div className="flex gap-2">
            {mockRouting.fallbacks.map((f, i) => (
              <span key={i} className="text-[11px] font-mono text-muted-foreground bg-accent rounded px-2 py-0.5">{f}</span>
            ))}
          </div>
        </div>
      </div>
    </AIPanel>
  );
}

/* ─── Beneficiary Name Matching ─── */
interface NameMatchResult {
  score: number;
  isMatch: boolean;
  method: string;
  registeredName: string;
  providedName: string;
  warnings: string[];
}

const mockNameMatch: NameMatchResult = {
  score: 0.92,
  isMatch: true,
  method: "Jaro-Winkler",
  registeredName: "ACME CORPORATION PVT LTD",
  providedName: "Acme Corp",
  warnings: ["Abbreviated name — matched via fuzzy matching"],
};

export function NameMatchPanel() {
  return (
    <AIPanel title="Name verification" confidence={Math.round(mockNameMatch.score * 100)}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-[11px] text-muted-foreground mb-1">Provided</p>
            <p className="font-mono text-[12px] text-foreground">{mockNameMatch.providedName}</p>
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground mb-1">Registered (bank)</p>
            <p className="font-mono text-[12px] text-foreground">{mockNameMatch.registeredName}</p>
          </div>
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-info/10">
          <div className="flex items-center gap-2">
            <StatusBadge status={mockNameMatch.isMatch ? "MATCH" : "MISMATCH"} variant={mockNameMatch.isMatch ? "success" : "destructive"} />
            <span className="text-[11px] text-muted-foreground font-mono">{mockNameMatch.method}</span>
          </div>
          <span className="font-mono text-[13px] text-foreground tabular">{(mockNameMatch.score * 100).toFixed(0)}%</span>
        </div>
        {mockNameMatch.warnings.length > 0 && (
          <div className="text-[11px] text-warning">{mockNameMatch.warnings.join(" · ")}</div>
        )}
      </div>
    </AIPanel>
  );
}

/* ─── Transaction Categorization ─── */
interface CategoryResult {
  primary: string;
  subcategory: string;
  confidence: number;
  merchantName: string;
  mcc: string;
}

const mockCategories: CategoryResult[] = [
  { primary: "vendor_payment", subcategory: "invoice_settlement", confidence: 96, merchantName: "Acme Corp", mcc: "5999" },
  { primary: "salary", subcategory: "monthly_payroll", confidence: 98, merchantName: "—", mcc: "—" },
  { primary: "subscription", subcategory: "saas_tool", confidence: 91, merchantName: "Notion Labs", mcc: "5817" },
];

export function TransactionCategorizationPanel() {
  return (
    <AIPanel title="Transaction categorization" badge="NLP">
      <div className="space-y-2">
        {mockCategories.map((cat, i) => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-info/10 last:border-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-[12px] text-foreground">{cat.primary}</span>
              <span className="text-[11px] text-muted-foreground">/ {cat.subcategory}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {cat.merchantName !== "—" && <span className="text-[11px] text-muted-foreground">{cat.merchantName}</span>}
              <span className={`font-mono text-[11px] ${cat.confidence >= 90 ? "text-success" : "text-warning"}`}>{cat.confidence}%</span>
            </div>
          </div>
        ))}
      </div>
    </AIPanel>
  );
}

/* ─── Cashflow Forecasting ─── */
interface ForecastPoint { day: string; predicted: string; lower: string; upper: string; }

const mockForecast: ForecastPoint[] = [
  { day: "Mar 8", predicted: "₹3.1Cr", lower: "₹2.7Cr", upper: "₹3.5Cr" },
  { day: "Mar 9", predicted: "₹2.8Cr", lower: "₹2.4Cr", upper: "₹3.2Cr" },
  { day: "Mar 10", predicted: "₹1.2Cr", lower: "₹0.9Cr", upper: "₹1.5Cr" },
  { day: "Mar 11", predicted: "₹3.4Cr", lower: "₹2.9Cr", upper: "₹3.9Cr" },
  { day: "Mar 12", predicted: "₹2.9Cr", lower: "₹2.5Cr", upper: "₹3.3Cr" },
  { day: "Mar 13", predicted: "₹3.6Cr", lower: "₹3.1Cr", upper: "₹4.1Cr" },
  { day: "Mar 14", predicted: "₹4.0Cr", lower: "₹3.4Cr", upper: "₹4.6Cr" },
];

export function CashflowForecastPanel() {
  return (
    <AIPanel title="Cashflow forecast" badge="7-day" confidence={87}>
      <div className="space-y-3">
        <div className="grid grid-cols-4 text-[10px] uppercase tracking-[0.04em] text-muted-foreground font-medium pb-2 border-b border-info/10">
          <span>Day</span>
          <span className="text-right">Predicted</span>
          <span className="text-right">Lower</span>
          <span className="text-right">Upper</span>
        </div>
        {mockForecast.map((f, i) => (
          <div key={i} className="grid grid-cols-4 py-1.5">
            <span className="text-[12px] text-foreground">{f.day}</span>
            <span className="text-right font-mono text-[12px] text-foreground tabular">{f.predicted}</span>
            <span className="text-right font-mono text-[11px] text-muted-foreground tabular">{f.lower}</span>
            <span className="text-right font-mono text-[11px] text-muted-foreground tabular">{f.upper}</span>
          </div>
        ))}
        <div className="pt-3 border-t border-info/10 space-y-1">
          <p className="text-[12px] text-foreground">
            <Sparkles className="w-3 h-3 text-info inline mr-1.5" />
            <span className="font-medium">Trend:</span> Upward — expected 15% increase next week
          </p>
          <p className="text-[12px] text-warning">
            ⚡ Anomaly: Mar 10 unusually low — possible holiday effect
          </p>
        </div>
      </div>
    </AIPanel>
  );
}

/* ─── Liveness & Deepfake Defense ─── */
interface LivenessResult {
  isLive: boolean;
  confidence: number;
  spoofType: string | null;
  checksPassed: { name: string; passed: boolean; detail: string }[];
}

const mockLiveness: LivenessResult = {
  isLive: true,
  confidence: 97,
  spoofType: null,
  checksPassed: [
    { name: "Texture analysis", passed: true, detail: "Natural skin texture detected" },
    { name: "Depth estimation", passed: true, detail: "3D face structure confirmed" },
    { name: "Moiré detection", passed: true, detail: "No screen artifacts" },
    { name: "Frame consistency", passed: true, detail: "Temporal coherence verified" },
    { name: "Deepfake detection", passed: true, detail: "No boundary artifacts or GAN signatures" },
  ],
};

export function LivenessPanel() {
  return (
    <AIPanel title="Liveness & deepfake defense" confidence={mockLiveness.confidence}>
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <StatusBadge status={mockLiveness.isLive ? "LIVE" : "SPOOF DETECTED"} variant={mockLiveness.isLive ? "success" : "destructive"} />
          {mockLiveness.spoofType && <span className="text-[12px] text-destructive font-mono">{mockLiveness.spoofType}</span>}
        </div>
        <div className="space-y-1.5">
          {mockLiveness.checksPassed.map((check, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-info/10 last:border-0">
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${check.passed ? "bg-success" : "bg-destructive"}`} />
                <span className="text-[12px] text-foreground">{check.name}</span>
              </div>
              <span className="text-[11px] text-muted-foreground">{check.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </AIPanel>
  );
}

/* ─── Enhanced Document AI (Tamper Detection) ─── */
interface TamperResult {
  isTampered: boolean;
  confidence: number;
  documentType: string;
  checks: { name: string; passed: boolean; detail: string }[];
}

const mockTamper: TamperResult = {
  isTampered: false,
  confidence: 95,
  documentType: "Scanned",
  checks: [
    { name: "Font consistency", passed: true, detail: "Uniform font family & sizing" },
    { name: "Metadata analysis", passed: true, detail: "Creation date consistent with document age" },
    { name: "Edge artifacts", passed: true, detail: "No splicing or overlay detected" },
    { name: "Compression analysis", passed: true, detail: "Single compression pass" },
  ],
};

export function TamperDetectionPanel() {
  return (
    <AIPanel title="Tamper & forgery detection" confidence={mockTamper.confidence}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <StatusBadge status={mockTamper.isTampered ? "TAMPER DETECTED" : "AUTHENTIC"} variant={mockTamper.isTampered ? "destructive" : "success"} />
          <span className="text-[11px] font-mono text-muted-foreground">{mockTamper.documentType} document</span>
        </div>
        <div className="space-y-1.5">
          {mockTamper.checks.map((check, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-info/10 last:border-0">
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${check.passed ? "bg-success" : "bg-destructive"}`} />
                <span className="text-[12px] text-foreground">{check.name}</span>
              </div>
              <span className="text-[11px] text-muted-foreground">{check.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </AIPanel>
  );
}

/* ─── Explainable Risk Queues ─── */
interface ExplainedAlert {
  id: string;
  entity: string;
  score: number;
  priorityRank: number;
  explanation: string;
  ruleContributions: { rule: string; weight: number }[];
  recommendedAction: string;
}

const mockExplainedAlerts: ExplainedAlert[] = [
  {
    id: "RSK-1203", entity: "Sunita Verma", score: 94, priorityRank: 1,
    explanation: "Partial name match against OFAC SDN list combined with recent large payout request. High severity due to sanctions implications.",
    ruleContributions: [
      { rule: "sanctions_name_match", weight: 0.45 },
      { rule: "amount_threshold", weight: 0.25 },
      { rule: "entity_age", weight: 0.15 },
      { rule: "geographic_risk", weight: 0.15 },
    ],
    recommendedAction: "Escalate to compliance. Freeze downstream payouts pending review.",
  },
  {
    id: "RSK-1204", entity: "Acme Corp", score: 78, priorityRank: 2,
    explanation: "Velocity threshold exceeded with 15 payouts in 5 minutes. Pattern consistent with automated batch processing but requires confirmation.",
    ruleContributions: [
      { rule: "velocity_check", weight: 0.50 },
      { rule: "amount_aggregation", weight: 0.30 },
      { rule: "time_pattern", weight: 0.20 },
    ],
    recommendedAction: "Review payout batch. Likely legitimate automation — confirm with ops.",
  },
];

export function ExplainableRiskPanel() {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <AIPanel title="Explainable risk queue" badge="Prioritized">
      <div className="space-y-3">
        {mockExplainedAlerts.map((alert) => (
          <div key={alert.id} className="rounded-lg border border-border bg-card overflow-hidden">
            <button
              className="flex items-center justify-between px-4 py-3 w-full text-left"
              onClick={() => setExpanded(expanded === alert.id ? null : alert.id)}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-[11px] font-mono text-muted-foreground w-6 shrink-0">#{alert.priorityRank}</span>
                <span className="text-[13px] font-medium text-foreground truncate">{alert.entity}</span>
                <span className="font-mono text-[11px] text-muted-foreground">{alert.id}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`font-mono text-[12px] tabular ${alert.score >= 90 ? "text-destructive" : "text-warning"}`}>{alert.score}</span>
                {expanded === alert.id ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
              </div>
            </button>
            {expanded === alert.id && (
              <div className="px-4 pb-4 space-y-3">
                <p className="text-[12px] text-foreground leading-relaxed">{alert.explanation}</p>
                <div>
                  <p className="text-[11px] text-muted-foreground mb-2">Rule contributions</p>
                  <div className="space-y-1.5">
                    {alert.ruleContributions.map((rc, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-accent rounded-full overflow-hidden">
                          <div className="h-full bg-info/60 rounded-full" style={{ width: `${rc.weight * 100}%` }} />
                        </div>
                        <span className="font-mono text-[10px] text-muted-foreground w-24 truncate">{rc.rule}</span>
                        <span className="font-mono text-[10px] text-foreground w-8 text-right tabular">{(rc.weight * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="pt-2 border-t border-border/50">
                  <p className="text-[11px] text-muted-foreground mb-1">Recommended action</p>
                  <p className="text-[12px] text-info">{alert.recommendedAction}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </AIPanel>
  );
}

/* ─── AI Recon Intelligence ─── */
interface ReconSuggestion {
  breakId: string;
  classification: string;
  resolutionPath: string;
  confidence: number;
  suggestedMatches: string[];
}

const mockReconAI: ReconSuggestion[] = [
  { breakId: "BRK-221", classification: "Provider fee deduction", resolutionPath: "Auto-resolve — create fee journal entry", confidence: 94, suggestedMatches: ["FEE-HDFC-0047"] },
  { breakId: "BRK-220", classification: "Delayed settlement reflection", resolutionPath: "Wait 24h — reversal in transit", confidence: 82, suggestedMatches: [] },
  { breakId: "BRK-219", classification: "Duplicate callback", resolutionPath: "Auto-deduplicated — mark resolved", confidence: 98, suggestedMatches: ["COL-88420-DUP"] },
];

export function ReconAIPanel() {
  return (
    <AIPanel title="AI recon intelligence" badge="Auto-match">
      <div className="space-y-2">
        {mockReconAI.map((item) => (
          <div key={item.breakId} className="flex flex-col sm:flex-row sm:items-center justify-between py-2.5 border-b border-info/10 last:border-0 gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[12px] text-foreground">{item.breakId}</span>
                <span className="text-[11px] text-muted-foreground">{item.classification}</span>
              </div>
              <p className="text-[11px] text-info mt-0.5">{item.resolutionPath}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {item.suggestedMatches.length > 0 && (
                <span className="font-mono text-[10px] text-muted-foreground bg-accent rounded px-1.5 py-0.5">{item.suggestedMatches[0]}</span>
              )}
              <span className={`font-mono text-[11px] ${item.confidence >= 90 ? "text-success" : "text-warning"}`}>{item.confidence}%</span>
            </div>
          </div>
        ))}
      </div>
    </AIPanel>
  );
}

/* ─── AI Collections Intelligence ─── */
interface CollectionInsight {
  vaId: string;
  vaName: string;
  priorityScore: number;
  predictedDate: string;
  predictedAmount: string;
  suggestedAction: string;
  confidence: number;
}

const mockCollections: CollectionInsight[] = [
  { vaId: "VA-9001", vaName: "Acme Corp Collections", priorityScore: 92, predictedDate: "Mar 8", predictedAmount: "₹12.4L", suggestedAction: "Expected — no follow-up needed", confidence: 91 },
  { vaId: "VA-9004", vaName: "QuickPay Settlements", priorityScore: 78, predictedDate: "Mar 9", predictedAmount: "₹8.2L", suggestedAction: "Send reminder via email — 2 days overdue", confidence: 84 },
  { vaId: "VA-9002", vaName: "Zenith Escrow", priorityScore: 45, predictedDate: "Mar 12", predictedAmount: "₹3.1L", suggestedAction: "Low priority — payment pattern normal", confidence: 76 },
];

export function CollectionsAIPanel() {
  return (
    <AIPanel title="Collections intelligence" badge="Predictions">
      <div className="space-y-3">
        {mockCollections.map((item) => (
          <div key={item.vaId} className="rounded-lg border border-border bg-card px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <div className="min-w-0">
                <span className="text-[13px] font-medium text-foreground">{item.vaName}</span>
                <span className="font-mono text-[11px] text-muted-foreground ml-2">{item.vaId}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[11px] text-muted-foreground">Priority</span>
                <span className={`font-mono text-[12px] tabular ${item.priorityScore >= 80 ? "text-foreground" : "text-muted-foreground"}`}>{item.priorityScore}</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
              <span className="text-muted-foreground">
                Expected: <span className="font-mono text-foreground">{item.predictedAmount}</span> by {item.predictedDate}
              </span>
              <span className={`${item.priorityScore >= 70 ? "text-info" : "text-muted-foreground"}`}>{item.suggestedAction}</span>
            </div>
          </div>
        ))}
      </div>
    </AIPanel>
  );
}