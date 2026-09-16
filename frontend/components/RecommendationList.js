function sourceLabel(source) {
  if (typeof source === "string") return source;
  if (source && typeof source === "object") {
    return source.page ? `${source.file} p.${source.page}` : source.file;
  }
  return String(source);
}

export default function RecommendationList({ recommendations, isEscalated }) {
  if (!recommendations || recommendations.length === 0) {
    if (isEscalated) {
      return (
        <p className="text-sm text-muted">
          Lifestyle assessment was stopped early because the patient reported symptoms needing
          prompt medical attention. No lifestyle recommendations were generated.
        </p>
      );
    }
    return <p className="text-sm text-muted">No recommendations generated.</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      {recommendations.map((rec, index) => (
        <div key={index} className="rounded-card border border-primary/10 bg-surface p-3">
          <span className="inline-block rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
            {rec.category}
          </span>
          <p className="mt-1 text-sm text-ink">{rec.text_english}</p>
          {rec.sources && rec.sources.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {rec.sources.map((source, i) => (
                <span
                  key={i}
                  className="rounded-full border border-muted/20 bg-page px-2 py-0.5 text-[10px] text-muted"
                >
                  {sourceLabel(source)}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
