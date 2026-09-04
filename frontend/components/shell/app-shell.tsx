"use client";

import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { ErrorBoundary } from "@/components/primitives/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useUser } from "@/lib/auth";
import { ROUTES } from "@/lib/routes";
import { Sidebar, type SidebarMode } from "./sidebar";
import { ThemeFromQuery } from "./theme-from-query";

const PUBLIC_PREFIXES = ["/dev"]; // mirrors middleware.ts

function nextMode(mode: SidebarMode, isWide: boolean): SidebarMode {
  if (mode === "auto") return isWide ? "collapsed" : "expanded";
  return mode === "collapsed" ? "expanded" : "collapsed";
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: me, error, isPending } = useUser();
  const [mode, setMode] = useState<SidebarMode>("auto");

  const isPublic = PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  const isSessionInvalid = error instanceof ApiError && error.isUnauthenticated;

  // Cookie present but session rejected by the API (expired, logged out elsewhere).
  useEffect(() => {
    if (isSessionInvalid && !isPublic) router.replace(`${ROUTES.login}?next=${encodeURIComponent(pathname)}`);
  }, [isSessionInvalid, isPublic, pathname, router]);

  const toggle = () => setMode((current) => nextMode(current, window.matchMedia("(min-width: 1024px)").matches));

  return (
    <div className="flex min-h-screen">
      <Suspense fallback={null}>
        <ThemeFromQuery />
      </Suspense>
      <Sidebar me={me} mode={mode} onToggle={toggle} />
      <main className="min-w-0 flex-1 px-6 py-6 lg:px-10">
        {isPending && !isPublic ? <ShellSkeleton /> : <ErrorBoundary>{children}</ErrorBoundary>}
      </main>
    </div>
  );
}

function ShellSkeleton() {
  return (
    <div className="space-y-4" aria-busy>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
