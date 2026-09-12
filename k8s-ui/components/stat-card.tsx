type StatCardProps = {
  label: string;
  value: string;
  detail: string;
  tone: "emerald" | "blue" | "amber" | "violet" | "rose";
};

const toneClasses: Record<StatCardProps["tone"], string> = {
  emerald: "bg-emerald-500/10 text-emerald-700 ring-1 ring-emerald-500/20 dark:text-emerald-300",
  blue: "bg-cyan-500/10 text-cyan-700 ring-1 ring-cyan-500/20 dark:text-cyan-300",
  amber: "bg-amber-500/10 text-amber-700 ring-1 ring-amber-500/20 dark:text-amber-300",
  violet: "bg-violet-500/10 text-violet-700 ring-1 ring-violet-500/20 dark:text-violet-300",
  rose: "bg-rose-500/10 text-rose-700 ring-1 ring-rose-500/20 dark:text-rose-300",
};

export function StatCard({ label, value, detail, tone }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className={`mb-4 inline-flex rounded-xl px-2 py-1 text-xs font-medium ${toneClasses[tone]}`}>
        {label}
      </div>
      <div className="text-3xl font-semibold text-foreground">{value}</div>
      <div className="mt-2 text-sm text-muted-foreground">{detail}</div>
    </div>
  );
}
