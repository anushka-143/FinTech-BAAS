import { useAuth } from "@/contexts/AuthContext";

export default function EnvironmentSwitcher() {
  const { user, switchEnvironment } = useAuth();
  if (!user) return null;

  return (
    <div className="flex items-center h-7 rounded-md border border-border bg-card overflow-hidden text-[11px] font-medium">
      <button
        onClick={() => switchEnvironment("production")}
        className={`px-3 h-full transition-colors ${
          user.environment === "production"
            ? "bg-foreground text-card"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        Production
      </button>
      <button
        onClick={() => switchEnvironment("sandbox")}
        className={`px-3 h-full transition-colors ${
          user.environment === "sandbox"
            ? "bg-foreground text-card"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        Sandbox
      </button>
    </div>
  );
}
