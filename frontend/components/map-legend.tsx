import { Card } from "@/components/ui/card";
import { formatEURCompact } from "@/lib/format";

const GRADIENT = "linear-gradient(to right, #f3f7f2, #c8e2d3, #7fb8ab, #3d8a76, #0c5a4a)";

export function MapLegend({ min, max }: { min: number; max: number }) {
  return (
    <Card className="w-48 gap-1 p-3 shadow-md">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Total lending
      </p>
      <div className="h-2.5 w-full rounded-full" style={{ background: GRADIENT }} />
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>{formatEURCompact(min)}</span>
        <span>{formatEURCompact(max)}</span>
      </div>
    </Card>
  );
}
