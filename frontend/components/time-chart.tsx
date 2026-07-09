"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatEURCompact } from "@/lib/format";
import type { YearTotal } from "@/lib/types";

const PRIMARY = "#0c5a4a";
const SECONDARY = "#8bbdb2";

export function TimeChart({ data }: { data: YearTotal[] }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(240 10% 90%)" />
        <XAxis
          dataKey="year"
          tick={{ fontSize: 11, fill: "hsl(240 4% 42%)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={30}
        />
        <YAxis
          tickFormatter={formatEURCompact}
          tick={{ fontSize: 11, fill: "hsl(240 4% 42%)" }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <Tooltip
          formatter={(value) => formatEURCompact(Number(value))}
          labelFormatter={(label) => `Year ${label}`}
          contentStyle={{
            fontSize: 12,
            borderRadius: 8,
            border: "1px solid hsl(240 10% 88%)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="total_eur"
          name="All sectors"
          stroke={PRIMARY}
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="climate_eur"
          name="Climate-relevant"
          stroke={SECONDARY}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
