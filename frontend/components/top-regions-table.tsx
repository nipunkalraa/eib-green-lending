import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatEUR } from "@/lib/format";
import type { TopRegion } from "@/lib/types";

export function TopRegionsTable({ regions }: { regions: TopRegion[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">#</TableHead>
          <TableHead>Region</TableHead>
          <TableHead className="text-right">Total lending</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {regions.map((region, i) => (
          <TableRow key={region.nuts_id}>
            <TableCell className="text-muted-foreground">{i + 1}</TableCell>
            <TableCell className="font-medium">{region.nuts_name}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatEUR(region.total_lending_eur)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
