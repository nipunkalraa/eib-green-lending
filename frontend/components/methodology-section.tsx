import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Summary } from "@/lib/types";

export function MethodologySection({ summary }: { summary: Summary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-serif text-xl">Methodology &amp; data</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>
          This dashboard reads static exports produced by a Python pipeline that loads European
          Investment Bank financed-project data, assigns each project a region, and merges it
          with Eurostat regional economic indicators. The full pipeline, including PDF
          extraction and the underlying methodology, is documented in the{" "}
          <a
            href="https://github.com/nipunkalraa/eib-green-lending"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-foreground underline underline-offset-2 hover:text-primary"
          >
            repository README
          </a>
          .
        </p>
        {summary.limitations.length > 0 && (
          <div>
            <p className="mb-2 font-medium text-foreground">Known limitations</p>
            <ul className="list-disc space-y-1.5 pl-5">
              {summary.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
