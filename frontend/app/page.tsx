import { readFile } from "node:fs/promises";
import path from "node:path";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatsRow } from "@/components/stats-row";
import { TopRegionsTable } from "@/components/top-regions-table";
import { MethodologySection } from "@/components/methodology-section";
import { SectorChart } from "@/components/sector-chart";
import { TimeChart } from "@/components/time-chart";
import { ChoroplethMap } from "@/components/choropleth-map";
import type { Summary } from "@/lib/types";

async function getSummary(): Promise<Summary> {
  const filePath = path.join(process.cwd(), "public", "data", "summary.json");
  const raw = await readFile(filePath, "utf-8");
  return JSON.parse(raw) as Summary;
}

export default async function Home() {
  const summary = await getSummary();

  return (
    <div className="mx-auto max-w-7xl space-y-16 px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
      {/* 1. Header / intro / stats */}
      <section className="space-y-6">
        <div className="max-w-3xl space-y-3">
          <h1 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
            EIB Green-Lending, by Region
          </h1>
          <p className="text-base text-muted-foreground sm:text-lg">
            Where the European Investment Bank&apos;s lending has gone since 1959, and how much
            of it is climate-relevant, built on real, publicly-sourced data.
          </p>
          <p className="text-base text-muted-foreground sm:text-lg">
            The EIB is the EU&apos;s climate bank and one of the largest sources of development
            finance in the world, yet its regional footprint is rarely visible at a glance. This
            dashboard makes that footprint explorable, region by region.
          </p>
        </div>
        <StatsRow summary={summary} />
      </section>

      {/* 2. Choropleth (placeholder for now) */}
      <section className="space-y-3">
        <h2 className="font-serif text-2xl font-semibold tracking-tight">
          Lending intensity by region
        </h2>
        <ChoroplethMap />
      </section>

      {/* 3. Supporting charts (placeholder for now) */}
      <section className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="font-serif text-xl">Lending by sector</CardTitle>
          </CardHeader>
          <CardContent>
            <SectorChart data={summary.sector_breakdown} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="font-serif text-xl">Lending over time</CardTitle>
          </CardHeader>
          <CardContent>
            <TimeChart data={summary.lending_over_time} />
          </CardContent>
        </Card>
      </section>

      {/* 4. Top 10 regions table */}
      <section className="space-y-3">
        <h2 className="font-serif text-2xl font-semibold tracking-tight">Top 10 regions</h2>
        <Card>
          <CardContent className="pt-6">
            <TopRegionsTable regions={summary.top_regions} />
          </CardContent>
        </Card>
      </section>

      {/* 5. Methodology & limitations */}
      <section className="space-y-3">
        <MethodologySection summary={summary} />
      </section>

      {/* 6. Outcomes / so what */}
      <section className="space-y-3">
        <Card>
          <CardHeader>
            <CardTitle className="font-serif text-xl">Outcomes and so what</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              The regional breakdown surfaces where EIB lending, and its climate share, concentrate
              or lag, patterns that are easy to assert but hard to see without linking project data
              to region-level geography. That link is what this pipeline builds.
            </p>
            <p>
              For research or policy use, it offers a reusable base for asking sharper questions,
              for example whether climate-relevant lending tracks regional need, or whether it
              follows existing capacity instead.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
