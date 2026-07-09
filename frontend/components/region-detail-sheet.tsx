"use client";

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatEUR, formatEURCompact, formatNumber, formatPercent } from "@/lib/format";
import type { RegionProperties } from "@/lib/types";

const PRIMARY = "#0c5a4a";

export function RegionDetailSheet({
  region,
  open,
  onOpenChange,
}: {
  region: RegionProperties | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-md">
        {region && (
          <>
            <SheetHeader>
              <SheetTitle className="font-serif text-2xl">{region.NUTS_NAME}</SheetTitle>
              <SheetDescription>{region.CNTR_CODE}</SheetDescription>
            </SheetHeader>

            <div className="mt-6 space-y-6">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Total lending
                </p>
                <p className="font-serif text-3xl font-semibold tabular-nums">
                  {formatEUR(region.total_lending_eur)}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Projects
                  </p>
                  <p className="text-lg font-semibold tabular-nums">
                    {formatNumber(region.project_count)}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Avg. per project
                  </p>
                  <p className="text-lg font-semibold tabular-nums">
                    {region.avg_lending_eur != null ? formatEURCompact(region.avg_lending_eur) : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Climate-relevant share
                  </p>
                  <p className="text-lg font-semibold tabular-nums">
                    {region.climate_share != null ? formatPercent(region.climate_share) : "—"}
                  </p>
                </div>
              </div>

              {region.top_sectors.length > 0 ? (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Top sectors
                  </p>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart
                      data={region.top_sectors}
                      layout="vertical"
                      margin={{ left: 8, right: 16, top: 0, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(240 10% 90%)" />
                      <XAxis type="number" hide />
                      <YAxis
                        type="category"
                        dataKey="sector"
                        width={110}
                        tick={{ fontSize: 11, fill: "hsl(240 4% 42%)" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip formatter={(value) => formatEURCompact(Number(value))} />
                      <Bar dataKey="total_eur" fill={PRIMARY} radius={[0, 4, 4, 0]} maxBarSize={14} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No sector breakdown available for this region.
                </p>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
