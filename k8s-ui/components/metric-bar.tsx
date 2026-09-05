type MetricBarProps = {
  label: string;
  value: string;
  percent: number | null;
  toneClass: string;
};

export function MetricBar({ label, value, percent, toneClass }: MetricBarProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={toneClass}>{value}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${percent === null ? "bg-slate-300" : "bg-slate-600"}`}
          style={{
            width: percent === null ? "0%" : `${Math.min(100, Math.max(0, percent))}%`,
            backgroundColor: percent === null ? undefined : toneFill(percent),
          }}
        />
      </div>
    </div>
  );
}

function toneFill(percent: number): string {
  if (percent >= 90) return "#dc2626";
  if (percent >= 70) return "#d97706";
  return "#22c55e";
}