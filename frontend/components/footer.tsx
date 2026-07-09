import { GithubIcon } from "@/components/github-icon";

const REPO_URL = "https://github.com/nipunkalraa/eib-green-lending";

export function Footer() {
  return (
    <footer className="border-t border-border/80 bg-secondary/40">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-2xl text-sm text-muted-foreground">
            <p>
              Built with AI assistance — human in the loop. Design decisions, data choices, and
              interpretations are my own.
            </p>
          </div>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium text-foreground transition-colors hover:text-primary"
          >
            <GithubIcon className="h-4 w-4" />
            Source on GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
