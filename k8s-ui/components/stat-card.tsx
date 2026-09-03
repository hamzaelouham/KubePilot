type StatCardProps = {
  label: string;
  value: string;
  detail: string;
  tone: "emerald" | "blue" | "amber" | "violet" | "rose";
};

const toneClasses: Record<StatCardProps["tone"], string> = {
  emerald: "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/20",
  blue: "bg-cyan-500/10 text-cyan-300 ring-1 ring-cyan-500/20",
  amber: "bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/20",
  violet: "bg-violet-500/10 text-violet-300 ring-1 ring-violet-500/20",
  rose: "bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/20",
};

export function StatCard({ label, value, detail, tone }: StatCardProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg shadow-slate-950/30">
      <div className={`mb-4 inline-flex rounded-xl px-2 py-1 text-xs font-medium ${toneClasses[tone]}`}>
        {label}
      </div>
      <div className="text-3xl font-semibold text-white">{value}</div>
      <div className="mt-2 text-sm text-slate-400">{detail}</div>
    </div>
  );
}
