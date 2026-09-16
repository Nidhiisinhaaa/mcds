export function TextField({ label, id, type = "text", value, onChange, required, ...rest }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        className="rounded-card border border-muted/30 bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        {...rest}
      />
    </label>
  );
}

export function SelectField({ label, id, value, onChange, children, required, ...rest }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <select
        id={id}
        name={id}
        value={value}
        onChange={onChange}
        required={required}
        className="rounded-card border border-muted/30 bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        {...rest}
      >
        {children}
      </select>
    </label>
  );
}

export function ErrorText({ children }) {
  if (!children) return null;
  return <p className="text-sm text-danger">{children}</p>;
}
