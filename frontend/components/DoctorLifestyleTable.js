"use client";

import { useState } from "react";

const SLOTS = [
  { key: "sleep", label: "Sleep", fields: [{ name: "sleep_hours", type: "number", unit: "hrs/day", step: "0.5" }] },
  {
    key: "exercise",
    label: "Exercise",
    fields: [
      { name: "exercise_days_per_week", type: "number", unit: "days/wk", step: "1" },
      { name: "exercise_minutes_per_session", type: "number", unit: "min/session", step: "1" },
    ],
  },
  {
    key: "diet",
    label: "Diet",
    fields: [
      {
        name: "diet_pattern",
        type: "select",
        options: ["balanced", "mixed", "frequent_fast_food", "high_sugar", "irregular"],
      },
    ],
  },
  {
    key: "water",
    label: "Water",
    fields: [{ name: "water_litres_per_day", type: "number", unit: "L/day", step: "0.1" }],
  },
  {
    key: "stress",
    label: "Stress",
    fields: [{ name: "stress_level", type: "select", options: ["low", "moderate", "high"] }],
  },
  {
    key: "sitting",
    label: "Sitting",
    fields: [{ name: "sitting_hours_per_day", type: "number", unit: "hrs/day", step: "0.5" }],
  },
  {
    key: "smoking",
    label: "Smoking",
    fields: [
      { name: "smoking_status", type: "select", options: ["none", "occasional", "daily"] },
      { name: "cigarettes_per_day", type: "number", unit: "cig/day", step: "1" },
    ],
  },
  {
    key: "alcohol",
    label: "Alcohol",
    fields: [
      { name: "alcohol_frequency", type: "select", options: ["none", "occasional", "weekly", "daily"] },
    ],
  },
];

function formatValue(value, unit, slotStatusValue) {
  if (value === null || value === undefined || value === "") {
    if (slotStatusValue === "skipped") return "Skipped (unanswered after follow-up)";
    return "Not answered";
  }
  const display = typeof value === "string" ? value.replaceAll("_", " ") : value;
  return unit ? `${display} ${unit}` : String(display);
}

export default function DoctorLifestyleTable({ lifestyleProfile, slotStatus, onSave, saving }) {
  const [editingSlot, setEditingSlot] = useState(null);
  const [draft, setDraft] = useState({});

  if (!lifestyleProfile) {
    return <p className="text-sm text-muted">No lifestyle data yet.</p>;
  }

  const overrides = lifestyleProfile.doctor_overrides || {};
  const evidence = lifestyleProfile.evidence || {};

  function effectiveValue(fieldName) {
    return fieldName in overrides ? overrides[fieldName] : lifestyleProfile[fieldName];
  }

  function startEdit(slot) {
    const initial = {};
    slot.fields.forEach((f) => {
      const value = effectiveValue(f.name);
      initial[f.name] = value === null || value === undefined ? "" : value;
    });
    setDraft(initial);
    setEditingSlot(slot.key);
  }

  async function save(slot) {
    const payload = {};
    slot.fields.forEach((f) => {
      const raw = draft[f.name];
      if (raw === "" || raw === undefined) return;
      payload[f.name] = f.type === "number" ? Number(raw) : raw;
    });
    if (Object.keys(payload).length === 0) {
      setEditingSlot(null);
      return;
    }
    await onSave(payload);
    setEditingSlot(null);
  }

  function isFilled(slot) {
    return slot.fields.some((f) => {
      const v = effectiveValue(f.name);
      return v !== null && v !== undefined && v !== "";
    });
  }

  const skippedLabels = SLOTS.filter((s) => slotStatus?.[s.key] === "skipped").map((s) => s.label);
  const unreportedLabels = SLOTS.filter(
    (s) => slotStatus?.[s.key] === "pending" || (!slotStatus && !isFilled(s))
  ).map((s) => s.label);

  return (
    <div>
      {(skippedLabels.length > 0 || unreportedLabels.length > 0) && (
        <p className="mb-2 rounded-card border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
          {skippedLabels.length > 0 && <>Skipped: {skippedLabels.join(", ")}. </>}
          {unreportedLabels.length > 0 && <>Unreported: {unreportedLabels.join(", ")}.</>}
        </p>
      )}
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs uppercase tracking-wide text-muted">
          <th className="py-2 pr-2">Factor</th>
          <th className="py-2 pr-2">Value</th>
          <th className="py-2"></th>
        </tr>
      </thead>
      <tbody>
        {SLOTS.map((slot) => {
          const isEditing = editingSlot === slot.key;
          const slotEvidence = evidence[slot.key];
          const isOverridden = slot.fields.some((f) => f.name in overrides);

          return (
            <tr key={slot.key} className="border-t border-primary/5">
              <td className="py-2 pr-2 align-top font-medium text-ink">{slot.label}</td>
              <td className="py-2 pr-2 align-top" title={slotEvidence?.quote || ""}>
                {isEditing ? (
                  <div className="flex flex-wrap items-center gap-2">
                    {slot.fields.map((f) =>
                      f.type === "select" ? (
                        <select
                          key={f.name}
                          value={draft[f.name] ?? ""}
                          onChange={(e) => setDraft((d) => ({ ...d, [f.name]: e.target.value }))}
                          className="rounded border border-muted/30 px-2 py-1 text-xs"
                        >
                          <option value="">-</option>
                          {f.options.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt.replaceAll("_", " ")}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          key={f.name}
                          type="number"
                          step={f.step || "1"}
                          value={draft[f.name] ?? ""}
                          onChange={(e) => setDraft((d) => ({ ...d, [f.name]: e.target.value }))}
                          placeholder={f.unit}
                          className="w-24 rounded border border-muted/30 px-2 py-1 text-xs"
                        />
                      )
                    )}
                  </div>
                ) : (
                  <span className="text-ink">
                    {slot.fields
                      .map((f) => formatValue(effectiveValue(f.name), f.unit, slotStatus?.[slot.key]))
                      .join(" / ")}
                    {isOverridden && (
                      <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                        edited
                      </span>
                    )}
                  </span>
                )}
              </td>
              <td className="py-2 text-right align-top">
                {isEditing ? (
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => save(slot)}
                      disabled={saving}
                      className="rounded bg-primary px-2 py-1 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingSlot(null)}
                      className="rounded border border-muted/30 px-2 py-1 text-xs text-muted"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => startEdit(slot)}
                    className="text-xs text-primary hover:underline"
                  >
                    Edit
                  </button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
    </div>
  );
}
