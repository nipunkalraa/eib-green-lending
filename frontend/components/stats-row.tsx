import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatEURCompact, formatNumber } from "@/lib/format";
import type { Summary } from "@/lib/types";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="font-serif text-2xl font-semibold tabular-nums sm:text-3xl">{value}</p>
        {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function StatsRow({ summary }: { summary: Summary }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard label="Total lending" value={formatEURCompact(summary.total_lending_eur)} />
      <StatCard
        label="Projects financed"
        value={formatNumber(summary.total_projects)}
        sub={`${formatNumber(summary.climate_relevant_projects)} climate-relevant`}
      />
      <StatCard label="Countries covered" value={formatNumber(summary.countries_covered)} />
      <StatCard
        label="Year range"
        value={`${summary.year_range[0]}–${summary.year_range[1]}`}
      />
    </div>
  );
}
