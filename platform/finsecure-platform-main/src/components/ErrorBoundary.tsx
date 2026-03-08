import { Component, ErrorInfo, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex items-center justify-center px-6">
          <div className="text-center max-w-[420px]">
            <div className="w-12 h-12 rounded-xl bg-destructive/10 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-6 h-6 text-destructive" />
            </div>
            <h2 className="text-[18px] font-semibold text-foreground mb-2">Something went wrong</h2>
            <p className="text-[13px] text-muted-foreground mb-1">
              An unexpected error occurred. Your data has been preserved.
            </p>
            {this.state.error && (
              <p className="text-[12px] font-mono text-muted-foreground/60 bg-accent/50 rounded-md px-3 py-2 mt-3 mb-4 break-all">
                {this.state.error.message}
              </p>
            )}
            <div className="flex gap-3 justify-center">
              <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
                Reload page
              </Button>
              <Button size="sm" onClick={() => this.setState({ hasError: false, error: null })}>
                Try again
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
