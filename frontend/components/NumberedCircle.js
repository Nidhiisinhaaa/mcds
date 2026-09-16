export default function NumberedCircle({ number, className = "" }) {
  return (
    <span
      className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary font-heading text-sm font-semibold text-white ${className}`}
    >
      {number}
    </span>
  );
}
