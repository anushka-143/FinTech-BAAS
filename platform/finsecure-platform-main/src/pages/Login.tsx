import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Navigate, Link } from "react-router-dom";
import { Eye, EyeOff, Loader2, Shield, CheckCircle2 } from "lucide-react";
import logoImage from "@/assets/logo.png";

export default function LoginPage() {
  const { login, verifyMFA, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("admin@demo-fintech.com");
  const [password, setPassword] = useState("demo1234");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaError, setMfaError] = useState("");

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result.requiresMFA) {
        setMfaRequired(true);
      }
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleMFA = async (e: React.FormEvent) => {
    e.preventDefault();
    setMfaError("");
    setMfaLoading(true);
    try {
      const success = await verifyMFA(mfaCode);
      if (!success) {
        setMfaError("Invalid verification code.");
      }
    } catch {
      setMfaError("Verification failed. Please try again.");
    } finally {
      setMfaLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left — brand panel */}
      <div className="hidden lg:flex lg:w-[520px] xl:w-[580px] flex-col justify-between p-14 relative"
        style={{ background: 'linear-gradient(180deg, hsl(40 10% 97%) 0%, hsl(40 8% 94%) 100%)' }}
      >
        {/* Brand */}
        <div>
          <div className="flex items-center gap-2.5 mb-20">
            <img src={logoImage} alt="FinStack" className="w-8 h-8 rounded-md" />
            <span className="text-[16px] font-semibold text-foreground tracking-[-0.03em]">FinStack</span>
          </div>

          <h2 className="text-[44px] xl:text-[48px] font-semibold text-foreground tracking-[-0.035em] leading-[1.08] mb-5">
            Financial<br />
            infrastructure,<br />
            built for scale.
          </h2>
          <p className="text-[15px] text-muted-foreground leading-[1.7] max-w-[340px]">
            Manage payouts, collections, KYC, reconciliation, and risk — all from one unified operating system.
          </p>
        </div>

        {/* Trust signals */}
        <div className="space-y-4">
          <div className="flex items-center gap-5">
            {["SOC 2 Type II", "PCI DSS", "ISO 27001"].map((cert) => (
              <div key={cert} className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3 h-3 text-primary/60" />
                <span className="text-[11px] font-medium text-muted-foreground tracking-wide uppercase">{cert}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right — auth form */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-16">
        <div className="w-full max-w-[380px]">
          {/* Mobile brand */}
          <div className="flex items-center gap-2.5 mb-12 lg:hidden">
            <img src={logoImage} alt="FinStack" className="w-8 h-8 rounded-md" />
            <span className="text-[16px] font-semibold text-foreground tracking-[-0.03em]">FinStack</span>
          </div>

          {!mfaRequired ? (
            <LoginForm
              email={email} setEmail={setEmail}
              password={password} setPassword={setPassword}
              showPassword={showPassword} setShowPassword={setShowPassword}
              loading={loading} error={error}
              onSubmit={handleLogin}
            />
          ) : (
            <MFAForm
              code={mfaCode} setCode={setMfaCode}
              loading={mfaLoading} error={mfaError}
              onSubmit={handleMFA}
              onBack={() => setMfaRequired(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/* ——— Login form sub-component ——— */
function LoginForm({
  email, setEmail, password, setPassword,
  showPassword, setShowPassword, loading, error, onSubmit,
}: {
  email: string; setEmail: (v: string) => void;
  password: string; setPassword: (v: string) => void;
  showPassword: boolean; setShowPassword: (v: boolean) => void;
  loading: boolean; error: string;
  onSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <>
      <h1 className="text-[26px] font-semibold text-foreground tracking-[-0.03em] mb-1">Sign in</h1>
      <p className="text-[14px] text-muted-foreground mb-9">Enter your credentials to continue.</p>

      {error && (
        <div className="mb-6 px-4 py-3 rounded-lg bg-destructive/5 border border-destructive/15 text-[13px] text-destructive font-medium">
          {error}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-5">
        <div className="space-y-2">
          <label htmlFor="email" className="block text-[12px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="w-full h-11 px-3.5 rounded-lg border border-input bg-card text-[14px] text-foreground placeholder:text-muted-foreground/50 transition-all duration-200"
            autoComplete="email"
            required
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label htmlFor="password" className="block text-[12px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              Password
            </label>
            <Link to="/forgot-password" className="text-[12px] font-medium text-primary/80 hover:text-primary transition-colors">
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full h-11 px-3.5 pr-11 rounded-lg border border-input bg-card text-[14px] text-foreground transition-all duration-200"
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground transition-colors"
            >
              {showPassword ? <EyeOff className="w-[15px] h-[15px]" /> : <Eye className="w-[15px] h-[15px]" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full h-11 rounded-lg bg-primary text-primary-foreground text-[14px] font-semibold tracking-[-0.01em] transition-all duration-200 hover:opacity-90 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none shadow-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Sign in"}
        </button>
      </form>

      <p className="mt-8 text-center text-[12px] text-muted-foreground/70">
        Don't have an account?{" "}
        <span className="text-primary/80 cursor-pointer hover:text-primary font-medium transition-colors">Contact your administrator</span>
      </p>
    </>
  );
}

/* ——— MFA form sub-component ——— */
function MFAForm({
  code, setCode, loading, error, onSubmit, onBack,
}: {
  code: string; setCode: (v: string) => void;
  loading: boolean; error: string;
  onSubmit: (e: React.FormEvent) => void;
  onBack: () => void;
}) {
  return (
    <>
      <div className="w-10 h-10 rounded-lg bg-primary/8 flex items-center justify-center mb-5">
        <Shield className="w-5 h-5 text-primary" />
      </div>
      <h1 className="text-[26px] font-semibold text-foreground tracking-[-0.03em] mb-1">Two-factor authentication</h1>
      <p className="text-[14px] text-muted-foreground mb-9">
        Enter the 6-digit code from your authenticator app.
      </p>

      {error && (
        <div className="mb-6 px-4 py-3 rounded-lg bg-destructive/5 border border-destructive/15 text-[13px] text-destructive font-medium">
          {error}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-5">
        <div className="space-y-2">
          <label htmlFor="mfa-code" className="block text-[12px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
            Verification code
          </label>
          <input
            id="mfa-code"
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={code}
            onChange={e => setCode(e.target.value.replace(/\D/g, ""))}
            placeholder="000000"
            className="w-full h-11 px-3.5 rounded-lg border border-input bg-card text-[15px] text-foreground font-mono tracking-[0.35em] text-center transition-all duration-200"
            autoFocus
            required
          />
        </div>
        <button
          type="submit"
          disabled={loading || code.length < 6}
          className="w-full h-11 rounded-lg bg-primary text-primary-foreground text-[14px] font-semibold tracking-[-0.01em] transition-all duration-200 hover:opacity-90 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none shadow-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Verify"}
        </button>
      </form>

      <button
        onClick={onBack}
        className="mt-5 w-full text-center text-[13px] text-muted-foreground/70 hover:text-foreground font-medium transition-colors"
      >
        ← Back to sign in
      </button>
    </>
  );
}
