export const BAND_COLORS = {
  Good: "#00C49A",
  Fair: "#00808A",
  "Needs attention": "#D98E04",
  Poor: "#B83A3A",
};

const BAND_CLASSES = {
  Good: "bg-mint/15 text-ink",
  Fair: "bg-primary/10 text-primary",
  "Needs attention": "bg-warning/15 text-warning",
  Poor: "bg-danger/15 text-danger",
};

export default function ScoreBadge({ total, band, status }) {
  if (total === null || total === undefined) {
    const isComplete = status === "completed" || status === "reviewed";
    return (
      <span className="text-xs text-muted">
        {isComplete ? "Not scored — insufficient responses" : "Not scored"}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
        BAND_CLASSES[band] || "bg-muted/10 text-muted"
      }`}
    >
      {total} &middot; {band}
    </span>
  );
}
