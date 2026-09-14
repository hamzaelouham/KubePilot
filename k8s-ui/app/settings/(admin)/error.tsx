"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function SettingsError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center gap-4 text-center" role="alert">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Settings could not be loaded</h1>
        <p className="mt-1 text-sm text-muted-foreground">The Settings authorization service is temporarily unavailable.</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <Button type="button" onClick={reset}>Try again</Button>
        <Button variant="outline" render={<Link href="/dashboard" />}>Back to dashboard</Button>
      </div>
    </div>
  );
}
