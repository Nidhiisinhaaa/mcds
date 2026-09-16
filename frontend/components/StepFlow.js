import NumberedCircle from "./NumberedCircle";

export default function StepFlow({ steps }) {
  return (
    <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
      {steps.map((step, index) => (
        <li
          key={step.title}
          className="flex flex-col gap-3 rounded-card border border-primary/15 bg-surface p-5"
        >
          <NumberedCircle number={index + 1} />
          <h3 className="font-heading text-base font-semibold text-ink">{step.title}</h3>
          <p className="text-sm text-muted">{step.body}</p>
        </li>
      ))}
    </ol>
  );
}
