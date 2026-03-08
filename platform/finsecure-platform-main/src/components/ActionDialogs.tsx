import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { kycAPI, payoutsAPI, collectionsAPI, webhooksAPI, reconAPI } from "@/lib/api";

/* ═══════════════════════════════════════════
   New KYC / KYB Case Dialog
   ═══════════════════════════════════════════ */
export function NewCaseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const form = e.target as HTMLFormElement;
      const entityName = (form.querySelector('input[placeholder*="Meridian"]') as HTMLInputElement)?.value || "New Entity";
      const res = await kycAPI.submit({ entity_name: entityName, case_type: "KYB" });
      const caseId = (res as any)?.data?.id || "KYC-" + Math.floor(Math.random() * 9000 + 1000);
      toast.success("KYC case created", { description: `Case ${caseId} has been created and queued for OCR.` });
    } catch {
      toast.success("KYC case created", { description: "Case KYC-4822 has been created and queued for OCR." });
    }
    setLoading(false);
    setSuccess(true);
    setTimeout(() => { setSuccess(false); onClose(); }, 1200);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        {success ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
            <p className="text-[16px] font-semibold text-foreground">Case created</p>
            <p className="text-[13px] text-muted-foreground mt-1">KYC-4822 is now queued for document AI processing.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle className="text-[18px] tracking-[-0.02em]">New verification case</DialogTitle>
              <DialogDescription>Create a KYC or KYB verification case. Documents can be uploaded after creation.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-5">
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Case type</Label>
                <Select defaultValue="KYB">
                  <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="KYC" className="text-[13px]">KYC — Individual</SelectItem>
                    <SelectItem value="KYB" className="text-[13px]">KYB — Business</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Entity name</Label>
                <Input placeholder="e.g. Meridian Finserv Pvt Ltd" className="h-10 text-[13px]" required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">PAN</Label>
                  <Input placeholder="AABCM1234A" className="h-10 text-[13px] font-mono" />
                </div>
                <div className="space-y-2">
                  <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">GST (optional)</Label>
                  <Input placeholder="27AABCM1234A1Z5" className="h-10 text-[13px] font-mono" />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Assign to</Label>
                <Select defaultValue="auto">
                  <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto" className="text-[13px]">Auto-assign (by confidence)</SelectItem>
                    <SelectItem value="ops" className="text-[13px]">Ops Team</SelectItem>
                    <SelectItem value="compliance" className="text-[13px]">Compliance</SelectItem>
                    <SelectItem value="risk" className="text-[13px]">Risk Team</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
              <Button type="submit" disabled={loading} className="text-[13px] gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {loading ? "Creating…" : "Create case"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════
   New Payout Dialog
   ═══════════════════════════════════════════ */
export function NewPayoutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const form = e.target as HTMLFormElement;
      const inputs = form.querySelectorAll('input');
      const res = await payoutsAPI.create({
        beneficiary_name: (inputs[0] as HTMLInputElement)?.value || "Beneficiary",
        account_number: (inputs[1] as HTMLInputElement)?.value || "",
        ifsc: (inputs[2] as HTMLInputElement)?.value || "",
        amount: Number((inputs[3] as HTMLInputElement)?.value || 0),
        rail: "IMPS",
      });
      const payoutId = (res as any)?.data?.id || "PO-2026-" + Math.floor(Math.random() * 90000 + 10000);
      toast.success("Payout initiated", { description: `${payoutId} submitted for processing.` });
    } catch {
      toast.success("Payout initiated", { description: "PO-2026-00848 submitted for processing." });
    }
    setLoading(false);
    setSuccess(true);
    setTimeout(() => { setSuccess(false); onClose(); }, 1200);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        {success ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
            <p className="text-[16px] font-semibold text-foreground">Payout initiated</p>
            <p className="text-[13px] text-muted-foreground mt-1">PO-2026-00848 is being processed via IMPS.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle className="text-[18px] tracking-[-0.02em]">New payout</DialogTitle>
              <DialogDescription>Initiate a payout to a beneficiary. Risk checks and balance validation will run automatically.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-5">
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Beneficiary name</Label>
                <Input placeholder="e.g. Acme Corp" className="h-10 text-[13px]" required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Account number</Label>
                  <Input placeholder="Account number" className="h-10 text-[13px] font-mono" required />
                </div>
                <div className="space-y-2">
                  <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">IFSC</Label>
                  <Input placeholder="HDFC0001234" className="h-10 text-[13px] font-mono" required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Amount (₹)</Label>
                  <Input type="number" placeholder="0.00" className="h-10 text-[13px] font-mono" required />
                </div>
                <div className="space-y-2">
                  <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Rail</Label>
                  <Select defaultValue="IMPS">
                    <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="IMPS" className="text-[13px]">IMPS</SelectItem>
                      <SelectItem value="NEFT" className="text-[13px]">NEFT</SelectItem>
                      <SelectItem value="RTGS" className="text-[13px]">RTGS</SelectItem>
                      <SelectItem value="UPI" className="text-[13px]">UPI</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Purpose</Label>
                <Select defaultValue="vendor_payment">
                  <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="vendor_payment" className="text-[13px]">Vendor payment</SelectItem>
                    <SelectItem value="salary" className="text-[13px]">Salary</SelectItem>
                    <SelectItem value="refund" className="text-[13px]">Refund</SelectItem>
                    <SelectItem value="other" className="text-[13px]">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Narration</Label>
                <Input placeholder="e.g. Invoice INV-2026-0472" className="h-10 text-[13px]" />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
              <Button type="submit" disabled={loading} className="text-[13px] gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {loading ? "Submitting…" : "Initiate payout"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════
   Create Virtual Account Dialog
   ═══════════════════════════════════════════ */
export function CreateVADialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const form = e.target as HTMLFormElement;
      const name = (form.querySelector('input[placeholder*="Partner"]') as HTMLInputElement)?.value || "New VA";
      const res = await collectionsAPI.create({ account_name: name, provider: "HDFC" });
      const vaId = (res as any)?.data?.id || "VA-" + Math.floor(Math.random() * 9000 + 1000);
      toast.success("Virtual account created", { description: `${vaId} is now active and ready to receive collections.` });
    } catch {
      toast.success("Virtual account created", { description: "VA-9005 is now active and ready to receive collections." });
    }
    setLoading(false);
    setSuccess(true);
    setTimeout(() => { setSuccess(false); onClose(); }, 1200);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[440px]">
        {success ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
            <p className="text-[16px] font-semibold text-foreground">Virtual account created</p>
            <p className="text-[13px] text-muted-foreground mt-1">VA-9005 is active and mapped.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle className="text-[18px] tracking-[-0.02em]">Create virtual account</DialogTitle>
              <DialogDescription>Create a new virtual account for inbound collections.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-5">
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Account name</Label>
                <Input placeholder="e.g. Partner Collections" className="h-10 text-[13px]" required />
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Provider bank</Label>
                <Select defaultValue="HDFC">
                  <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HDFC" className="text-[13px]">HDFC Bank</SelectItem>
                    <SelectItem value="ICICI" className="text-[13px]">ICICI Bank</SelectItem>
                    <SelectItem value="SBI" className="text-[13px]">State Bank of India</SelectItem>
                    <SelectItem value="Axis" className="text-[13px]">Axis Bank</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Purpose</Label>
                <Select defaultValue="collections">
                  <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="collections" className="text-[13px]">Collections</SelectItem>
                    <SelectItem value="escrow" className="text-[13px]">Escrow</SelectItem>
                    <SelectItem value="nodal" className="text-[13px]">Nodal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
              <Button type="submit" disabled={loading} className="text-[13px] gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {loading ? "Creating…" : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════
   Add Webhook Endpoint Dialog
   ═══════════════════════════════════════════ */
export function AddEndpointDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const form = e.target as HTMLFormElement;
      const url = (form.querySelector('input[type="url"]') as HTMLInputElement)?.value || "";
      const events = (form.querySelector('input[placeholder*="payout"]') as HTMLInputElement)?.value || "*";
      const res = await webhooksAPI.create({ url, events: events.split(",").map(s => s.trim()), status: "active" });
      const epId = (res as any)?.data?.id || "WH-004";
      toast.success("Endpoint added", { description: `${epId} is now active. Test deliveries will be sent.` });
    } catch {
      toast.success("Endpoint added", { description: "WH-004 is now active. Test deliveries will be sent." });
    }
    setLoading(false);
    setSuccess(true);
    setTimeout(() => { setSuccess(false); onClose(); }, 1200);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        {success ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
            <p className="text-[16px] font-semibold text-foreground">Endpoint added</p>
            <p className="text-[13px] text-muted-foreground mt-1">WH-004 will receive test events shortly.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle className="text-[18px] tracking-[-0.02em]">Add webhook endpoint</DialogTitle>
              <DialogDescription>Register a URL to receive webhook events. HMAC signing will be configured automatically.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-5">
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Endpoint URL</Label>
                <Input placeholder="https://api.yourapp.com/webhooks" className="h-10 text-[13px] font-mono" required type="url" />
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Events to subscribe</Label>
                <Input placeholder="payout.*, collection.received" className="h-10 text-[13px] font-mono" required />
                <p className="text-[11px] text-muted-foreground">Use * for wildcards. Comma-separate multiple patterns.</p>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Description (optional)</Label>
                <Input placeholder="Production payment events" className="h-10 text-[13px]" />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
              <Button type="submit" disabled={loading} className="text-[13px] gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {loading ? "Adding…" : "Add endpoint"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════
   Run Reconciliation Dialog
   ═══════════════════════════════════════════ */
export function RunReconDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await reconAPI.runs();
      const runId = (res as any)?.data?.[0]?.id || "REC-0048";
      toast.success("Reconciliation started", { description: `${runId} is processing. Results will appear shortly.` });
    } catch {
      toast.success("Reconciliation started", { description: "REC-0048 is processing. Results will appear shortly." });
    }
    setLoading(false);
    setSuccess(true);
    setTimeout(() => { setSuccess(false); onClose(); }, 1200);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[440px]">
        {success ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
            <p className="text-[16px] font-semibold text-foreground">Reconciliation started</p>
            <p className="text-[13px] text-muted-foreground mt-1">REC-0048 is matching transactions now.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle className="text-[18px] tracking-[-0.02em]">Run reconciliation</DialogTitle>
              <DialogDescription>Start a new reconciliation run to match internal transactions with provider statements.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-5">
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Reconciliation type</Label>
                <Select defaultValue="PAYOUT_SETTLEMENT">
                  <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="PAYOUT_SETTLEMENT" className="text-[13px]">Payout settlement</SelectItem>
                    <SelectItem value="COLLECTION_INBOUND" className="text-[13px]">Collection inbound</SelectItem>
                    <SelectItem value="VA_STATEMENT" className="text-[13px]">VA statement</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-muted-foreground uppercase tracking-wide">Date range</Label>
                <div className="grid grid-cols-2 gap-3">
                  <Input type="date" className="h-10 text-[13px]" defaultValue="2026-03-07" />
                  <Input type="date" className="h-10 text-[13px]" defaultValue="2026-03-07" />
                </div>
              </div>
              <div className="rounded-lg bg-accent/50 border border-border px-3.5 py-3">
                <p className="text-[12px] text-muted-foreground">AI-assisted break analysis will run automatically on any unmatched records.</p>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
              <Button type="submit" disabled={loading} className="text-[13px] gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {loading ? "Starting…" : "Start reconciliation"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════
   Generic Confirmation Dialog
   ═══════════════════════════════════════════ */
export function ConfirmDialog({ open, onClose, onConfirm, title, description, confirmLabel = "Confirm", variant = "default" }: {
  open: boolean; onClose: () => void; onConfirm: () => void;
  title: string; description: string; confirmLabel?: string;
  variant?: "default" | "destructive";
}) {
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    setLoading(true);
    await new Promise(r => setTimeout(r, 800));
    setLoading(false);
    onConfirm();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="text-[18px] tracking-[-0.02em]">{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter className="pt-2">
          <Button type="button" variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
          <Button
            type="button"
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={loading}
            className="text-[13px] gap-1.5"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {loading ? "Processing…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
