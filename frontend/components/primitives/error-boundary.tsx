"use client";

import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Custom fallback; receives the error and a reset callback. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.props.onError?.(error, info);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return (
      <div role="alert" className="flex flex-col items-center rounded-card border border-danger bg-surface px-6 py-10 text-center">
        <AlertTriangle size={24} strokeWidth={ICON_STROKE} className="text-danger" aria-hidden />
        <h3 className="mt-3 font-semibold">Something went wrong</h3>
        <p className="mt-1 max-w-md text-sm text-muted">{error.message}</p>
        <Button variant="outline" size="sm" className="mt-5" onClick={this.reset}>
          Try again
        </Button>
      </div>
    );
  }
}
