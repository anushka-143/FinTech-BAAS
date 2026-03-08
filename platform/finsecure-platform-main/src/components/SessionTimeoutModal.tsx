import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Clock } from "lucide-react";

export default function SessionTimeoutModal() {
  const { sessionTimeoutVisible, dismissSessionTimeout, logout } = useAuth();

  return (
    <Dialog open={sessionTimeoutVisible} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-[400px] p-0 gap-0" onPointerDownOutside={e => e.preventDefault()}>
        <div className="p-6 text-center">
          <div className="w-12 h-12 rounded-xl bg-warning/10 flex items-center justify-center mx-auto mb-4">
            <Clock className="w-6 h-6 text-warning" />
          </div>
          <h2 className="text-[18px] font-semibold text-foreground mb-1.5">Session expiring</h2>
          <p className="text-[14px] text-muted-foreground leading-relaxed">
            Your session will expire in 5 minutes due to inactivity. Would you like to continue?
          </p>
        </div>
        <div className="flex gap-3 px-6 pb-6">
          <Button variant="outline" className="flex-1 h-9 text-[13px]" onClick={logout}>
            Sign out
          </Button>
          <Button className="flex-1 h-9 text-[13px]" onClick={dismissSessionTimeout}>
            Continue session
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
