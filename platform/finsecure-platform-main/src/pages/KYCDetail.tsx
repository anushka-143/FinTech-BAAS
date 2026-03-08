import { useParams } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import Breadcrumbs from "@/components/Breadcrumbs";
import AuditTimeline from "@/components/AuditTimeline";
import StatusBadge from "@/components/StatusBadge";
import { LivenessPanel, TamperDetectionPanel } from "@/components/AIFeaturePanels";
import { ConfirmDialog } from "@/components/ActionDialogs";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2, XCircle, FileText, Download,
  Cpu, User, AlertTriangle,
} from "lucide-react";

const kycData: Record<string, any> = {
  "KYC-4821": {
    id: "KYC-4821", entity: "Meridian Finserv Pvt Ltd", type: "KYB", status: "IN_REVIEW",
    docs: [
      { name: "Certificate of Incorporation", type: "PDF", size: "1.2 MB", ocrStatus: "EXTRACTED", confidence: 92 },
      { name: "GST Registration", type: "PDF", size: "890 KB", ocrStatus: "EXTRACTED", confidence: 88 },
      { name: "Board Resolution", type: "PDF", size: "2.1 MB", ocrStatus: "EXTRACTED", confidence: 84 },
      { name: "PAN Card", type: "JPG", size: "340 KB", ocrStatus: "EXTRACTED", confidence: 95 },
    ],
    overallConfidence: 87, assignee: "Ops Team", created: "Mar 7, 2026 12:30",
    cin: "U74999MH2020PTC123456", pan: "AABCM1234A", gst: "27AABCM1234A1Z5",
    directors: ["Vikram Mehta", "Anjali Desai"], registeredAddress: "101, Tower B, BKC, Mumbai 400051",
    aiSummary: "KYB documents verified via OCR. All 4 documents successfully extracted. CIN and PAN cross-verified against MCA records. GST registration matches PAN. Board resolution is valid. Overall confidence 87% — recommend manual review for Board Resolution (84% confidence).",
    aiRecommendation: "approve_with_review",
  },
  "KYC-4816": {
    id: "KYC-4816", entity: "Sunita Verma", type: "KYC", status: "SANCTIONS_HIT",
    docs: [
      { name: "Aadhaar Card", type: "JPG", size: "280 KB", ocrStatus: "EXTRACTED", confidence: 96 },
      { name: "PAN Card", type: "JPG", size: "190 KB", ocrStatus: "EXTRACTED", confidence: 94 },
    ],
    overallConfidence: 78, assignee: "Compliance", created: "Mar 7, 2026 09:30",
    pan: "BVMPV1234K",
    aiSummary: "OFAC sanctions screening returned a potential match. Name 'Sunita Verma' matches SDN list entry with 78% confidence. PAN and Aadhaar successfully extracted. Recommend compliance review before proceeding.",
    aiRecommendation: "escalate_compliance",
    sanctionsDetails: { list: "OFAC SDN", matchScore: 78, matchedName: "Sunita Verma", matchedCountry: "India" },
  },
};

const reviewTimeline = [
  { id: "t1", time: "12:35", title: "Assigned to Ops Team", description: "Auto-assigned based on confidence threshold.", type: "system" as const },
  { id: "t2", time: "12:34", title: "AI analysis completed", description: "87% overall confidence. Recommend approve with manual review.", type: "ai" as const },
  { id: "t3", time: "12:33", title: "OCR extraction completed", description: "4/4 documents processed successfully.", type: "system" as const },
  { id: "t4", time: "12:32", title: "Documents uploaded", description: "4 documents received via API.", type: "user" as const, actor: "System · API" },
  { id: "t5", time: "12:30", title: "KYB case created", description: "Entity: Meridian Finserv Pvt Ltd", type: "user" as const, actor: "System · API" },
];

export default function KYCDetail() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const kycCase = kycData[id || ""] || kycData["KYC-4821"];
  const isSanctions = kycCase.status === "SANCTIONS_HIT";
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);

  const sv = (s: string) => {
    if (s === "APPROVED") return "success" as const;
    if (s === "PENDING_OCR" || s === "IN_REVIEW") return "warning" as const;
    if (s === "REJECTED" || s === "SANCTIONS_HIT") return "destructive" as const;
    return "default" as const;
  };

  return (
    <DashboardLayout title="KYC case" subtitle={kycCase.id}>
      <Breadcrumbs items={[
        { label: "KYC / KYB", path: "/kyc" },
        { label: kycCase.id },
      ]} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <h2 className="text-[20px] md:text-[24px] font-semibold text-foreground tracking-[-0.02em]">{kycCase.entity}</h2>
            <StatusBadge status={kycCase.status} variant={sv(kycCase.status)} />
            <span className="text-[12px] font-mono text-muted-foreground bg-accent rounded px-2 py-0.5">{kycCase.type}</span>
          </div>
          <p className="text-[13px] text-muted-foreground">
            Confidence: <span className={`font-mono font-medium ${kycCase.overallConfidence >= 90 ? "text-success" : kycCase.overallConfidence >= 70 ? "text-warning" : "text-destructive"}`}>{kycCase.overallConfidence}%</span>
            {" · "}Assigned to {kycCase.assignee} · Created {kycCase.created}
          </p>
        </div>
        {hasPermission("canApproveKYC") && (
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" className="h-8 text-[12px] gap-1.5 text-destructive border-destructive/30 hover:bg-destructive/5" onClick={() => setRejectOpen(true)}>
              <XCircle className="w-3.5 h-3.5" />Reject
            </Button>
            <Button size="sm" className="h-8 text-[12px] gap-1.5" onClick={() => setApproveOpen(true)}>
              <CheckCircle2 className="w-3.5 h-3.5" />Approve
            </Button>
          </div>
        )}
      </div>

      {/* Sanctions alert */}
      {isSanctions && kycCase.sanctionsDetails && (
        <div className="mb-6 px-4 py-3.5 rounded-lg bg-destructive/6 border border-destructive/15">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-destructive">Sanctions screening match</p>
              <p className="text-[12px] text-destructive/70 mt-1">
                List: <span className="font-mono">{kycCase.sanctionsDetails.list}</span> · Match: <span className="font-mono">{kycCase.sanctionsDetails.matchScore}%</span> · Matched name: {kycCase.sanctionsDetails.matchedName}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6">
        {/* Left — details */}
        <div className="lg:col-span-5 space-y-4 md:space-y-6">
          {/* AI Summary */}
          <div className="rounded-lg border border-info/20 bg-info/4 overflow-hidden">
            <div className="flex items-center gap-2 px-4 md:px-5 py-3 border-b border-info/10">
              <Cpu className="w-4 h-4 text-info" />
              <span className="text-[13px] font-medium text-info">AI analysis</span>
              <span className="text-[10px] text-info/60 ml-auto font-mono">inference</span>
            </div>
            <div className="px-4 md:px-5 py-4">
              <p className="text-[13px] text-foreground leading-relaxed">{kycCase.aiSummary}</p>
            </div>
          </div>

          {/* AI Liveness & Tamper Detection */}
          <LivenessPanel />
          <TamperDetectionPanel />

          {/* Entity info */}
          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Entity details</span>
            </div>
            <div className="px-4 md:px-5 py-1">
              {[
                { label: "Case ID", value: kycCase.id },
                { label: "Type", value: kycCase.type },
                ...(kycCase.cin ? [{ label: "CIN", value: kycCase.cin }] : []),
                { label: "PAN", value: kycCase.pan },
                ...(kycCase.gst ? [{ label: "GST", value: kycCase.gst }] : []),
                ...(kycCase.registeredAddress ? [{ label: "Address", value: kycCase.registeredAddress }] : []),
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-3 border-b border-border/40 last:border-0 gap-2">
                  <span className="text-[12px] text-muted-foreground shrink-0">{item.label}</span>
                  <span className="font-mono text-[12px] text-foreground text-right break-all">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Documents */}
          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Documents ({kycCase.docs.length})</span>
            </div>
            <div className="divide-y divide-border/50">
              {kycCase.docs.map((doc: any, i: number) => (
                <div key={i} className="flex items-center justify-between px-4 md:px-5 py-3.5">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium text-foreground truncate">{doc.name}</p>
                      <p className="text-[11px] text-muted-foreground">{doc.type} · {doc.size}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`font-mono text-[11px] ${doc.confidence >= 90 ? "text-success" : doc.confidence >= 80 ? "text-warning" : "text-destructive"}`}>
                      {doc.confidence}%
                    </span>
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => toast.info("Download started", { description: doc.name })}>
                      <Download className="w-3.5 h-3.5 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Directors */}
          {kycCase.directors && (
            <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
              <div className="px-4 md:px-5 py-3.5 border-b border-border">
                <span className="text-section text-foreground">Directors</span>
              </div>
              <div className="divide-y divide-border/50">
                {kycCase.directors.map((d: string, i: number) => (
                  <div key={i} className="flex items-center gap-3 px-4 md:px-5 py-3">
                    <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center shrink-0">
                      <User className="w-3.5 h-3.5 text-muted-foreground" />
                    </div>
                    <span className="text-[13px] text-foreground">{d}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right — timeline */}
        <div className="lg:col-span-7">
          <AuditTimeline events={reviewTimeline} title="Case timeline" />

          {/* Notes section */}
          <div className="mt-4 md:mt-6 rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Internal notes</span>
            </div>
            <div className="px-4 md:px-5 py-4">
              <textarea
                className="w-full h-24 text-[13px] bg-accent/30 border border-border rounded-lg px-3 py-2.5 resize-none placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Add a note for the team…"
              />
              <div className="flex justify-end mt-2">
                <Button size="sm" className="h-8 text-[12px] px-3" onClick={() => toast.success("Note added")}>Add note</Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={approveOpen}
        onClose={() => setApproveOpen(false)}
        onConfirm={() => toast.success("Case approved", { description: `${kycCase.entity} has been approved.` })}
        title="Approve verification"
        description={`Approve ${kycCase.entity} (${kycCase.type})? This will enable downstream features and permissions for this entity.`}
        confirmLabel="Approve"
      />
      <ConfirmDialog
        open={rejectOpen}
        onClose={() => setRejectOpen(false)}
        onConfirm={() => toast.success("Case rejected", { description: `${kycCase.entity} has been rejected.` })}
        title="Reject verification"
        description={`Reject ${kycCase.entity} (${kycCase.type})? The entity will be notified and can re-submit documents.`}
        confirmLabel="Reject"
        variant="destructive"
      />
    </DashboardLayout>
  );
}
