import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Link, Navigate } from "react-router-dom";
import { Loader2, CheckCircle2, Eye, EyeOff } from "lucide-react";
import logoImage from "@/assets/logo.png";

export default function ResetPasswordPage() {
  const { resetPassword, isAuthenticated } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  if (isAuthenticated) return <Navigate to="/" replace />;

  const requirements = [
    { label: "At least 12 characters", met: password.length >= 12 },
    { label: "One uppercase letter", met: /[A-Z]/.test(password) },
    { label: "One number", met: /\d/.test(password) },
    { label: "One special character", met: /[!@#$%^&*(),.?":{}|<>]/.test(password) },
  ];

  const allMet = requirements.every(r => r.met);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (!allMet) return;
    setError("");
    setLoading(true);
    await resetPassword("mock-token", password);
    setDone(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-6">
      <div className="w-full max-w-[380px]">
        <div className="flex items-center gap-2.5 mb-12">
          <img src={logoImage} alt="FinStack" className="w-8 h-8 rounded-md" />
          <span className="text-[16px] font-semibold text-foreground tracking-[-0.03em]">FinStack</span>
        </div>

        {!done ? (
          <>
            <h1 className="text-[26px] font-semibold text-foreground tracking-[-0.03em] mb-1">Set new password</h1>
            <p className="text-[14px] text-muted-foreground mb-9">Choose a strong password for your account.</p>

            {error && (
              <div className="mb-6 px-4 py-3 rounded-lg bg-destructive/5 border border-destructive/15 text-[13px] text-destructive font-medium">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="password" className="block text-[12px] font-medium text-muted-foreground uppercase tracking-[0.04em]">New password</label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="w-full h-11 px-3.5 pr-11 rounded-lg border border-input bg-card text-[14px] text-foreground transition-all duration-200"
                    required
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground transition-colors">
                    {showPassword ? <EyeOff className="w-[15px] h-[15px]" /> : <Eye className="w-[15px] h-[15px]" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                {requirements.map(r => (
                  <div key={r.label} className="flex items-center gap-2 text-[12px]">
                    <div className={`w-1.5 h-1.5 rounded-full transition-colors ${r.met ? "bg-success" : "bg-border"}`} />
                    <span className={r.met ? "text-success" : "text-muted-foreground/60"}>{r.label}</span>
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                <label htmlFor="confirm" className="block text-[12px] font-medium text-muted-foreground uppercase tracking-[0.04em]">Confirm password</label>
                <input
                  id="confirm"
                  type="password"
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  className="w-full h-11 px-3.5 rounded-lg border border-input bg-card text-[14px] text-foreground transition-all duration-200"
                  required
                />
              </div>

              <button type="submit" disabled={loading || !allMet}
                className="w-full h-11 rounded-lg bg-primary text-primary-foreground text-[14px] font-semibold tracking-[-0.01em] transition-all duration-200 hover:opacity-90 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none shadow-sm">
                {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Reset password"}
              </button>
            </form>
          </>
        ) : (
          <div className="text-center">
            <div className="w-12 h-12 rounded-xl bg-success/8 flex items-center justify-center mx-auto mb-5">
              <CheckCircle2 className="w-6 h-6 text-success" />
            </div>
            <h1 className="text-[26px] font-semibold text-foreground tracking-[-0.03em] mb-2">Password updated</h1>
            <p className="text-[14px] text-muted-foreground mb-6">
              Your password has been successfully reset.
            </p>
            <Link to="/login">
              <button className="h-11 px-8 rounded-lg bg-primary text-primary-foreground text-[14px] font-semibold tracking-[-0.01em] transition-all duration-200 hover:opacity-90 active:scale-[0.99] shadow-sm">
                Sign in
              </button>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
