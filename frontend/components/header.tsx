import { GithubIcon } from "@/components/github-icon";

const REPO_URL = "https://github.com/nipunkalraa/eib-green-lending";

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/80 bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-baseline gap-2">
          <span className="font-serif text-base font-semibold tracking-tight sm:text-lg">
            EIB Green-Lending
          </span>
          <span className="hidden text-sm text-muted-foreground sm:inline">
            Regional Dashboard
          </span>
        </div>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <GithubIcon className="h-4 w-4" />
          <span className="hidden sm:inline">View on GitHub</span>
        </a>
      </div>
    </header>
  );
}
