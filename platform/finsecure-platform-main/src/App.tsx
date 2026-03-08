import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import SessionTimeoutModal from "@/components/SessionTimeoutModal";
import CommandPalette from "@/components/CommandPalette";
import ErrorBoundary from "@/components/ErrorBoundary";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Payouts from "./pages/Payouts";
import PayoutDetail from "./pages/PayoutDetail";
import KYC from "./pages/KYC";
import KYCDetail from "./pages/KYCDetail";
import Collections from "./pages/Collections";
import Ledger from "./pages/Ledger";
import Risk from "./pages/Risk";
import Reconciliation from "./pages/Reconciliation";
import ReconBreakDetail from "./pages/ReconBreakDetail";
import AICopilot from "./pages/AICopilot";
import Webhooks from "./pages/Webhooks";
import Events from "./pages/Events";
import SettingsPage from "./pages/Settings";
import ProfilePage from "./pages/Profile";
import TeamPage from "./pages/Team";
import AuditLogPage from "./pages/AuditLog";
import CasesPage from "./pages/Cases";
import ApprovalsPage from "./pages/Approvals";
import NotificationsPage from "./pages/Notifications";
import LoginPage from "./pages/Login";
import ForgotPasswordPage from "./pages/ForgotPassword";
import ResetPasswordPage from "./pages/ResetPassword";
import OnboardingPage from "./pages/Onboarding";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <ErrorBoundary>
            <SessionTimeoutModal />
            <CommandPalette />
            <Routes>
              {/* Public */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/onboarding" element={<ProtectedRoute><OnboardingPage /></ProtectedRoute>} />

              {/* Protected */}
              <Route path="/" element={<ProtectedRoute><Index /></ProtectedRoute>} />
              <Route path="/payouts" element={<ProtectedRoute requiredPermission="canViewPayouts"><Payouts /></ProtectedRoute>} />
              <Route path="/payouts/:id" element={<ProtectedRoute requiredPermission="canViewPayouts"><PayoutDetail /></ProtectedRoute>} />
              <Route path="/kyc" element={<ProtectedRoute requiredPermission="canViewKYC"><KYC /></ProtectedRoute>} />
              <Route path="/kyc/:id" element={<ProtectedRoute requiredPermission="canViewKYC"><KYCDetail /></ProtectedRoute>} />
              <Route path="/collections" element={<ProtectedRoute requiredPermission="canViewCollections"><Collections /></ProtectedRoute>} />
              <Route path="/ledger" element={<ProtectedRoute requiredPermission="canViewLedger"><Ledger /></ProtectedRoute>} />
              <Route path="/risk" element={<ProtectedRoute requiredPermission="canViewRisk"><Risk /></ProtectedRoute>} />
              <Route path="/reconciliation" element={<ProtectedRoute requiredPermission="canViewRecon"><Reconciliation /></ProtectedRoute>} />
              <Route path="/reconciliation/:id" element={<ProtectedRoute requiredPermission="canViewRecon"><ReconBreakDetail /></ProtectedRoute>} />
              <Route path="/ai-copilot" element={<ProtectedRoute requiredPermission="canViewAICopilot"><AICopilot /></ProtectedRoute>} />
              <Route path="/webhooks" element={<ProtectedRoute requiredPermission="canViewWebhooks"><Webhooks /></ProtectedRoute>} />
              <Route path="/events" element={<ProtectedRoute requiredPermission="canViewEvents"><Events /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute requiredPermission="canViewSettings"><SettingsPage /></ProtectedRoute>} />
              <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
              <Route path="/team" element={<ProtectedRoute requiredPermission="canManageTeam"><TeamPage /></ProtectedRoute>} />
              <Route path="/audit-log" element={<ProtectedRoute><AuditLogPage /></ProtectedRoute>} />
              <Route path="/cases" element={<ProtectedRoute requiredPermission="canViewCases"><CasesPage /></ProtectedRoute>} />
              <Route path="/approvals" element={<ProtectedRoute requiredPermission="canViewApprovals"><ApprovalsPage /></ProtectedRoute>} />
              <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />

              <Route path="*" element={<NotFound />} />
            </Routes>
          </ErrorBoundary>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
