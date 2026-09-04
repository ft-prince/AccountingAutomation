import type { Metadata } from "next";
import { ForecastView } from "@/components/forecast/forecast-view";

export const metadata: Metadata = { title: "Forecast · Nexren Finance" };

export default function ForecastPage() {
  return <ForecastView />;
}
