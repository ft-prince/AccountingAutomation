import { Construction } from "lucide-react";
import { notFound } from "next/navigation";
import { EmptyState } from "@/components/primitives/empty-state";
import { APP_NAV } from "@/lib/routes";

// Placeholder for every §11 route not yet built; real pages replace this as phases land
// (static routes take precedence over this dynamic segment).
export default async function SectionPlaceholderPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const route = APP_NAV.find((item) => item.href === `/${section}`);
  if (!route) notFound();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{route.label}</h1>
      <EmptyState icon={Construction} title={`${route.label} is not built yet`} description="This route is reserved by PROJECT_SPECS §11 and will be implemented in a later phase." />
    </div>
  );
}

export function generateStaticParams() {
  return APP_NAV.filter((item) => item.href !== "/dashboard").map((item) => ({ section: item.href.slice(1) }));
}
