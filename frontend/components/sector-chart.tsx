"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatEURCompact } from "@/lib/format";
import type { SectorTotal } from "@/lib/types";

const PRIMARY = "#0c5a4a";

export function SectorChart({ data }: { data: SectorTotal[] }) {
  const sorted = [...data].sort((a, b) => b.total_eur - a.total_eur);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={sorted} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(240 10% 90%)" />
        <XAxis
          type="number"
          tickFormatter={formatEURCompact}
          tick={{ fontSize: 11, fill: "hsl(240 4% 42%)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="sector"
          width={140}
          tick={{ fontSize: 11, fill: "hsl(240 4% 42%)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value) => formatEURCompact(Number(value))}
          contentStyle={{
            fontSize: 12,
            borderRadius: 8,
            border: "1px solid hsl(240 10% 88%)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
          }}
        />
        <Bar dataKey="total_eur" fill={PRIMARY} radius={[0, 4, 4, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}
