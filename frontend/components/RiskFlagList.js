const SEVERITY_CLASSES = {
  low: "border-muted bg-muted/5",
  medium: "border-warning bg-warning/5",
  high: "border-danger bg-danger/5",
};

export default function RiskFlagList({ flags }) {
  if (!flags || flags.length === 0) {
    return <p className="text-sm text-muted">No risk flags.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {flags.map((flag, index) => (
        <div
          key={index}
          className={`rounded-card border-l-4 px-3 py-2 ${SEVERITY_CLASSES[flag.severity] || SEVERITY_CLASSES.low}`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-ink">{flag.label}</span>
            <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-muted">
              {flag.severity}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted">{flag.reason}</p>
        </div>
      ))}
    </div>
  );
}
