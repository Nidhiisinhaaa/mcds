const STATUS_CLASSES = {
  in_progress: "bg-primary/10 text-primary",
  completed: "bg-mint/15 text-ink",
  reviewed: "bg-muted/15 text-muted",
  escalated: "bg-danger/15 text-danger",
};

const STATUS_LABELS = {
  in_progress: "In progress",
  completed: "Completed",
  reviewed: "Reviewed",
  escalated: "Escalated",
};

export default function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
        STATUS_CLASSES[status] || "bg-muted/10 text-muted"
      }`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}
