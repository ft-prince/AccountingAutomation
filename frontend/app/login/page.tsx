import type { Metadata } from "next";
import { LoginForm } from "@/components/login/login-form";
import { DEFAULT_BRAND_NAME } from "@/lib/routes";

export const metadata: Metadata = { title: `Sign in · ${DEFAULT_BRAND_NAME}` };

export default function LoginPage() {
  return (
    <main className="cream-wash flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <p className="font-display text-lg italic">
          {DEFAULT_BRAND_NAME}
          <span className="text-accent">.</span>
        </p>
        <h1 className="mt-6 text-4xl font-semibold tracking-tight">
          Finance, <em className="font-display italic font-normal text-accent">handled</em>.
        </h1>
        <p className="mt-3 text-sm text-muted">Sign in to your organisation&apos;s workspace.</p>
        <div className="mt-8 rounded-card border border-border bg-surface p-6">
          <LoginForm />
        </div>
      </div>
    </main>
  );
}
