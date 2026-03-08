import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Link, Navigate } from "react-router-dom";
import { ArrowLeft, Loader2, Mail } from "lucide-react";
import logoImage from "@/assets/logo.png";

export default function ForgotPasswordPage() {
  const { forgotPassword, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  if (isAuthenticated) return <Navigate to="/" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await forgotPassword(email);
    setSent(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-6">
      <div className="w-full max-w-[380px]">
        <div className="flex items-center gap-2.5 mb-12">
          <img src={logoImage} alt="FinStack" className="w-8 h-8 rounded-md" />
          <span className="text-[16px] font-semibold text-foreground tracking-[-0.03em]">FinStack</span>
        </div>

        {!sent ? (
          <>
            <h1 className="text-[26px] font-semibold text-foreground tracking-[-0.03em] mb-1">Reset password</h1>
            <p className="text-[14px] text-muted-foreground mb-9">
              Enter your email and we'll send you a reset link.
            </p>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="email" className="block text-[12px] font-medium text-muted-foreground uppercase tracking-[0.04em]">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full h-11 px-3.5 rounded-lg border border-input bg-card text-[14px] text-foreground placeholder:text-muted-foreground/50 transition-all duration-200"
                  required
                />
              </div>
              <button type="submit" disabled={loading}
                className="w-full h-11 rounded-lg bg-primary text-primary-foreground text-[14px] font-semibold tracking-[-0.01em] transition-all duration-200 hover:opacity-90 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none shadow-sm">
                {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Send reset link"}
              </button>
            </form>
          </>
        ) : (
          <div className="text-center">
            <div className="w-12 h-12 rounded-xl bg-success/8 flex items-center justify-center mx-auto mb-5">
              <Mail className="w-6 h-6 text-success" />
            </div>
            <h1 className="text-[26px] font-semibold text-foreground tracking-[-0.03em] mb-2">Check your email</h1>
            <p className="text-[14px] text-muted-foreground mb-6 leading-relaxed">
              We sent a password reset link to<br />
              <span className="font-medium text-foreground">{email}</span>
            </p>
            <p className="text-[12px] text-muted-foreground/70">
              Didn't receive the email?{" "}
              <button onClick={() => setSent(false)} className="text-primary/80 hover:text-primary font-medium transition-colors">
                Try again
              </button>
            </p>
          </div>
        )}

        <Link
          to="/login"
          className="flex items-center gap-1.5 justify-center mt-8 text-[13px] text-muted-foreground/70 hover:text-foreground font-medium transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to sign in
        </Link>
      </div>
    </div>
  );
}
