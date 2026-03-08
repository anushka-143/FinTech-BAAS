import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Shield, Loader2 } from "lucide-react";

interface StepUpAuthDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  description?: string;
}

export default function StepUpAuthDialog({ open, onClose, onConfirm, title = "Confirm your identity", description = "This action requires additional verification." }: StepUpAuthDialogProps) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length < 6) return;
    setLoading(true);
    setError("");
    // Simulate verification
    await new Promise(r => setTimeout(r, 600));
    if (code.length >= 6) {
      onConfirm();
      setCode("");
      setLoading(false);
    } else {
      setError("Invalid code. Please try again.");
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) { onClose(); setCode(""); setError(""); } }}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center mb-2">
            <Shield className="w-5 h-5 text-warning" />
          </div>
          <DialogTitle className="text-[18px]">{title}</DialogTitle>
          <DialogDescription className="text-[13px]">{description}</DialogDescription>
        </DialogHeader>

        {error && (
          <div className="px-4 py-3 rounded-lg bg-destructive/8 border border-destructive/20 text-[13px] text-destructive">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <div className="space-y-2">
            <Label htmlFor="step-up-code" className="text-[13px]">Authenticator code</Label>
            <Input
              id="step-up-code"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder="000000"
              className="h-10 font-mono tracking-[0.3em] text-center"
              autoFocus
            />
          </div>
          <div className="flex gap-3">
            <Button type="button" variant="outline" className="flex-1 h-9 text-[13px]" onClick={onClose}>Cancel</Button>
            <Button type="submit" className="flex-1 h-9 text-[13px]" disabled={loading || code.length < 6}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Confirm"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
