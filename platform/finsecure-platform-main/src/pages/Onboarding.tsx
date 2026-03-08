import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building2, User, ChevronRight, ChevronLeft, Loader2, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const industries = [
  "Banking & Financial Services",
  "Payments & Fintech",
  "Lending & Credit",
  "Insurance",
  "Wealth Management",
  "E-commerce",
  "SaaS & Technology",
  "Healthcare",
  "Education",
  "Other",
];

const roles = [
  "Founder / CEO",
  "CTO / VP Engineering",
  "Head of Product",
  "Head of Operations",
  "Head of Compliance",
  "Finance Manager",
  "Developer / Engineer",
  "Analyst",
  "Other",
];

const steps = [
  { id: "company", title: "Your company", subtitle: "Tell us about your organization", icon: Building2 },
  { id: "role", title: "Your role", subtitle: "Help us personalize your experience", icon: User },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { completeOnboarding } = useAuth();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("");
  const [userRole, setUserRole] = useState("");

  const canProceed = step === 0 ? companyName.trim().length > 0 && industry.length > 0 : userRole.length > 0;

  const handleNext = async () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
      return;
    }
    setLoading(true);
    await new Promise(r => setTimeout(r, 1000));
    completeOnboarding({ companyName: companyName.trim(), industry, userRole });
    setLoading(false);
    setDone(true);
    setTimeout(() => navigate("/"), 1200);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-[480px]">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2 flex-1">
              <div className={`h-1 rounded-full flex-1 transition-colors duration-300 ${i <= step ? "bg-primary" : "bg-border"}`} />
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {done ? (
            <motion.div
              key="done"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center py-12"
            >
              <CheckCircle2 className="w-12 h-12 text-success mx-auto mb-4" />
              <h2 className="text-[22px] font-semibold text-foreground tracking-[-0.02em]">You're all set</h2>
              <p className="text-[14px] text-muted-foreground mt-2">Taking you to your dashboard…</p>
            </motion.div>
          ) : (
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <div className="mb-6">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                  {(() => { const Icon = steps[step].icon; return <Icon className="w-5 h-5 text-primary" />; })()}
                </div>
                <h1 className="text-[24px] font-semibold text-foreground tracking-[-0.02em]">{steps[step].title}</h1>
                <p className="text-[14px] text-muted-foreground mt-1">{steps[step].subtitle}</p>
              </div>

              <div className="rounded-xl border border-border bg-card shadow-card p-6 space-y-5">
                {step === 0 && (
                  <>
                    <div className="space-y-2">
                      <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Company name</label>
                      <Input
                        value={companyName}
                        onChange={e => setCompanyName(e.target.value)}
                        placeholder="e.g. Acme Financial Services"
                        className="h-11 text-[14px]"
                        autoFocus
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Industry</label>
                      <Select value={industry} onValueChange={setIndustry}>
                        <SelectTrigger className="h-11 text-[14px]">
                          <SelectValue placeholder="Select your industry" />
                        </SelectTrigger>
                        <SelectContent>
                          {industries.map(i => (
                            <SelectItem key={i} value={i} className="text-[13px]">{i}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                )}

                {step === 1 && (
                  <div className="space-y-2">
                    <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Your role</label>
                    <Select value={userRole} onValueChange={setUserRole}>
                      <SelectTrigger className="h-11 text-[14px]">
                        <SelectValue placeholder="Select your role" />
                      </SelectTrigger>
                      <SelectContent>
                        {roles.map(r => (
                          <SelectItem key={r} value={r} className="text-[13px]">{r}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between mt-6">
                {step > 0 ? (
                  <Button variant="ghost" size="sm" className="text-[13px] gap-1.5" onClick={() => setStep(step - 1)}>
                    <ChevronLeft className="w-4 h-4" /> Back
                  </Button>
                ) : (
                  <div />
                )}
                <Button
                  onClick={handleNext}
                  disabled={!canProceed || loading}
                  className="text-[13px] gap-1.5 h-10 px-6"
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Setting up…</>
                  ) : step < steps.length - 1 ? (
                    <>Continue <ChevronRight className="w-4 h-4" /></>
                  ) : (
                    <>Get started <ChevronRight className="w-4 h-4" /></>
                  )}
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
