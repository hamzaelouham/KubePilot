import Link from "next/link";
import { Boxes } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12 text-foreground">
      <div className="w-full max-w-xl rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Boxes aria-hidden="true" className="size-5" />
          </span>
          <h1 className="text-2xl font-semibold text-foreground">KubePilot</h1>
        </div>
        <p className="mt-6 text-base leading-7 text-muted-foreground">
          A production-ready control plane for cluster health, workload visibility, and platform operations.
        </p>

        <div className="mt-8 space-y-3">
          <Button className="w-full" render={<Link href="/login" />}>Go to login</Button>
          <Button className="w-full" variant="outline" render={<Link href="/dashboard" />}>Open dashboard preview</Button>
        </div>
      </div>
    </main>
  );
}
