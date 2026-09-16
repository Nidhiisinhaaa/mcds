import { t } from "@/lib/i18n";

export const SLOT_ORDER = [
  "sleep",
  "exercise",
  "diet",
  "water",
  "stress",
  "sitting",
  "smoking",
  "alcohol",
];

const SLOT_LABEL_KEYS = {
  sleep: "consult.slotSleep",
  exercise: "consult.slotExercise",
  diet: "consult.slotDiet",
  water: "consult.slotWater",
  stress: "consult.slotStress",
  sitting: "consult.slotSitting",
  smoking: "consult.slotSmoking",
  alcohol: "consult.slotAlcohol",
};

const STATE_CLASSES = {
  filled: "border-mint bg-mint/15 text-ink",
  skipped: "border-muted/30 bg-muted/10 text-muted opacity-70",
  pending: "border-muted/30 bg-surface text-muted",
};

export default function ProgressChips({ slotStatus = {}, lang = "en" }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SLOT_ORDER.map((slot) => {
        const state = slotStatus[slot] || "pending";
        return (
          <span
            key={slot}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${STATE_CLASSES[state]}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                state === "filled" ? "bg-mint" : state === "skipped" ? "bg-muted" : "bg-muted/40"
              }`}
              aria-hidden="true"
            />
            {t(SLOT_LABEL_KEYS[slot], lang)}
          </span>
        );
      })}
    </div>
  );
}
