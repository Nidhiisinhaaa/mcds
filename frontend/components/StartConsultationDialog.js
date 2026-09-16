"use client";

import { useEffect, useState } from "react";
import { SelectField, TextField, ErrorText } from "@/components/FormField";
import { createDoctorConsultation, createDoctorPatient, searchDoctorPatients } from "@/lib/api";
import { firstErrorMessage } from "@/lib/errors";

const LANGUAGES = ["en", "hi", "mr", "ta", "te", "bn", "kn", "gu", "ml"];
const LANGUAGE_LABELS = {
  en: "English",
  hi: "Hindi",
  mr: "Marathi",
  ta: "Tamil",
  te: "Telugu",
  bn: "Bengali",
  kn: "Kannada",
  gu: "Gujarati",
  ml: "Malayalam",
};

const EMPTY_NEW_PATIENT = {
  full_name: "",
  age: "",
  sex: "",
  height_cm: "",
  weight_kg: "",
  preferred_language: "en",
};

export default function StartConsultationDialog({ onClose, onStarted }) {
  const [mode, setMode] = useState("existing"); // existing | new
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [newPatient, setNewPatient] = useState(EMPTY_NEW_PATIENT);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (mode !== "existing" || !query.trim()) return undefined;
    const handle = setTimeout(async () => {
      setSearching(true);
      const result = await searchDoctorPatients(query.trim());
      setSearching(false);
      if (result.ok) setResults(result.data.results || result.data || []);
    }, 300);
    return () => clearTimeout(handle);
  }, [query, mode]);

  const showResults = mode === "existing" && query.trim().length > 0;

  function updateNewPatient(field) {
    return (e) => setNewPatient((p) => ({ ...p, [field]: e.target.value }));
  }

  function selectPatient(patient) {
    setSelectedPatient(patient);
    setQuery(patient.full_name || patient.username);
    setResults([]);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    let patientId = selectedPatient?.id;

    setSubmitting(true);
    if (mode === "new") {
      if (!newPatient.full_name.trim()) {
        setError("Patient name is required.");
        setSubmitting(false);
        return;
      }
      const payload = {
        full_name: newPatient.full_name.trim(),
        preferred_language: newPatient.preferred_language,
      };
      if (newPatient.age) payload.age = Number(newPatient.age);
      if (newPatient.sex) payload.sex = newPatient.sex;
      if (newPatient.height_cm) payload.height_cm = Number(newPatient.height_cm);
      if (newPatient.weight_kg) payload.weight_kg = Number(newPatient.weight_kg);

      const created = await createDoctorPatient(payload);
      if (!created.ok) {
        setError(firstErrorMessage(created.data, "Could not create the patient record."));
        setSubmitting(false);
        return;
      }
      patientId = created.data.id;
    }

    if (!patientId) {
      setError("Pick an existing patient, or switch to “New patient”.");
      setSubmitting(false);
      return;
    }

    const consultation = await createDoctorConsultation({ patientId });
    setSubmitting(false);
    if (!consultation.ok) {
      setError(firstErrorMessage(consultation.data, "Could not start the consultation."));
      return;
    }
    onStarted(consultation.data.id);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4">
      <div className="w-full max-w-md rounded-card border border-primary/10 bg-surface p-6 shadow-lg">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-lg font-semibold text-ink">Start consultation</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-muted hover:text-primary"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="mt-4 flex rounded-full border border-primary/20 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setMode("existing")}
            className={`flex-1 rounded-full px-3 py-1.5 ${
              mode === "existing" ? "bg-primary text-white" : "text-muted"
            }`}
          >
            Existing patient
          </button>
          <button
            type="button"
            onClick={() => setMode("new")}
            className={`flex-1 rounded-full px-3 py-1.5 ${
              mode === "new" ? "bg-primary text-white" : "text-muted"
            }`}
          >
            New patient
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {mode === "existing" ? (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="patient-search" className="text-sm font-medium text-ink">
                Search by name
              </label>
              <input
                id="patient-search"
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSelectedPatient(null);
                }}
                placeholder="Start typing a patient's name..."
                autoComplete="off"
                className="rounded-card border border-muted/30 bg-page px-3 py-2 text-sm text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
              {searching && <p className="text-xs text-muted">Searching...</p>}
              {showResults && results.length > 0 && (
                <ul className="max-h-48 overflow-y-auto rounded-card border border-primary/10">
                  {results.map((patient) => (
                    <li key={patient.id}>
                      <button
                        type="button"
                        onClick={() => selectPatient(patient)}
                        className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm hover:bg-page"
                      >
                        <span className="font-medium text-ink">
                          {patient.full_name || patient.username}
                        </span>
                        <span className="text-xs text-muted">
                          {[patient.age && `${patient.age} yrs`, patient.sex]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {selectedPatient && (
                <p className="rounded-card bg-mint/10 px-3 py-2 text-xs text-ink">
                  Selected: <span className="font-medium">{selectedPatient.full_name}</span>
                </p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <TextField
                id="new-patient-full-name"
                label="Full name"
                value={newPatient.full_name}
                onChange={updateNewPatient("full_name")}
                required
              />
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  id="new-patient-age"
                  label="Age"
                  type="number"
                  min="0"
                  value={newPatient.age}
                  onChange={updateNewPatient("age")}
                />
                <SelectField
                  id="new-patient-sex"
                  label="Sex"
                  value={newPatient.sex}
                  onChange={updateNewPatient("sex")}
                >
                  <option value="">-</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </SelectField>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  id="new-patient-height"
                  label="Height (cm)"
                  type="number"
                  step="0.1"
                  value={newPatient.height_cm}
                  onChange={updateNewPatient("height_cm")}
                />
                <TextField
                  id="new-patient-weight"
                  label="Weight (kg)"
                  type="number"
                  step="0.1"
                  value={newPatient.weight_kg}
                  onChange={updateNewPatient("weight_kg")}
                />
              </div>
              <SelectField
                id="new-patient-language"
                label="Preferred language"
                value={newPatient.preferred_language}
                onChange={updateNewPatient("preferred_language")}
              >
                {LANGUAGES.map((code) => (
                  <option key={code} value={code}>
                    {LANGUAGE_LABELS[code]}
                  </option>
                ))}
              </SelectField>
            </div>
          )}

          <ErrorText>{error}</ErrorText>

          <div className="mt-1 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-card border border-muted/30 px-4 py-2 text-sm text-muted hover:bg-page"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-card bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
            >
              {submitting ? "Starting..." : "Start consultation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
