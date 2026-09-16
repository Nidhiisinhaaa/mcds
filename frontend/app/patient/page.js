"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TextField, SelectField, ErrorText } from "@/components/FormField";
import { getMe, patchMe, listConsultations, createConsultation, logout } from "@/lib/api";
import { firstErrorMessage } from "@/lib/errors";
import { t } from "@/lib/i18n";
import { useRequireAuth } from "@/lib/useRequireAuth";

const PATIENT_LANGUAGES = ["en", "hi", "mr", "ta", "te", "bn", "kn", "gu", "ml"];

const STATUS_KEYS = {
  in_progress: "patient.statusInProgress",
  completed: "patient.statusCompleted",
  reviewed: "patient.statusReviewed",
  escalated: "patient.statusEscalated",
};

const STATUS_CLASSES = {
  in_progress: "bg-primary/10 text-primary",
  completed: "bg-mint/15 text-ink",
  reviewed: "bg-mint/15 text-ink",
  escalated: "bg-danger/10 text-danger",
};

export default function PatientDashboardPage() {
  useRequireAuth();
  const router = useRouter();

  const [profile, setProfile] = useState(null);
  const [consultations, setConsultations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [startError, setStartError] = useState("");
  const [starting, setStarting] = useState(false);

  const lang = profile?.preferred_language || "en";

  useEffect(() => {
    (async () => {
      const [meResult, consultationsResult] = await Promise.all([getMe(), listConsultations()]);
      if (meResult.ok) setProfile(meResult.data.profile || {});
      if (consultationsResult.ok) {
        setConsultations(consultationsResult.data.results || consultationsResult.data || []);
      }
      setLoading(false);
    })();
  }, []);

  function updateProfile(field) {
    return (e) => {
      const value = e.target.value;
      setProfile((p) => ({ ...p, [field]: value === "" ? null : value }));
    };
  }

  async function handleProfileSave(e) {
    e.preventDefault();
    setSaveError("");
    setSaving(true);
    const result = await patchMe({
      profile: {
        age: profile.age ? Number(profile.age) : null,
        sex: profile.sex || "",
        height_cm: profile.height_cm ? Number(profile.height_cm) : null,
        weight_kg: profile.weight_kg ? Number(profile.weight_kg) : null,
        preferred_language: profile.preferred_language || "en",
      },
    });
    setSaving(false);
    if (!result.ok) {
      setSaveError(firstErrorMessage(result.data, t("common.genericError", lang)));
      return;
    }
    setProfile(result.data.profile);
  }

  async function handleStartConsultation() {
    setStartError("");
    setStarting(true);
    const result = await createConsultation(profile?.preferred_language);
    setStarting(false);
    if (!result.ok) {
      if (result.status === 403) {
        router.push("/consent");
        return;
      }
      setStartError(firstErrorMessage(result.data, t("common.genericError", lang)));
      return;
    }
    router.push(`/patient/consult/${result.data.id}`);
  }

  if (loading) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-muted">{t("common.loading", "en")}</p>
      </main>
    );
  }

  return (
    <main className="flex-1 bg-page">
      <header className="border-b border-primary/10 bg-surface">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <span className="font-heading text-lg font-semibold text-ink">
            {t("common.appName", lang)}
          </span>
          <button
            type="button"
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-sm text-muted hover:text-primary"
          >
            {t("common.back", lang)}
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="font-heading text-2xl font-semibold text-ink">
          {t("patient.welcomeTitle", lang)}
        </h1>

        <section className="mt-8 rounded-card border border-primary/10 bg-surface p-6">
          <h2 className="font-heading text-lg font-semibold text-ink">
            {t("patient.profileTitle", lang)}
          </h2>
          <p className="mt-1 text-sm text-muted">{t("patient.profileSubtitle", lang)}</p>

          <form onSubmit={handleProfileSave} className="mt-5 grid gap-4 sm:grid-cols-2">
            <TextField
              id="age"
              type="number"
              min="0"
              max="120"
              label={t("patient.age", lang)}
              value={profile?.age ?? ""}
              onChange={updateProfile("age")}
            />
            <SelectField
              id="sex"
              label={t("patient.sex", lang)}
              value={profile?.sex ?? ""}
              onChange={updateProfile("sex")}
            >
              <option value="">-</option>
              <option value="male">{t("patient.sexMale", lang)}</option>
              <option value="female">{t("patient.sexFemale", lang)}</option>
              <option value="other">{t("patient.sexOther", lang)}</option>
            </SelectField>
            <TextField
              id="height_cm"
              type="number"
              min="0"
              step="0.1"
              label={t("patient.heightCm", lang)}
              value={profile?.height_cm ?? ""}
              onChange={updateProfile("height_cm")}
            />
            <TextField
              id="weight_kg"
              type="number"
              min="0"
              step="0.1"
              label={t("patient.weightKg", lang)}
              value={profile?.weight_kg ?? ""}
              onChange={updateProfile("weight_kg")}
            />
            <SelectField
              id="preferred_language"
              label={t("patient.preferredLanguage", lang)}
              value={profile?.preferred_language ?? "en"}
              onChange={updateProfile("preferred_language")}
            >
              {PATIENT_LANGUAGES.map((code) => (
                <option key={code} value={code}>
                  {t(`languages.${code}`, lang)}
                </option>
              ))}
            </SelectField>

            <div className="sm:col-span-2">
              <ErrorText>{saveError}</ErrorText>
              <button
                type="submit"
                disabled={saving}
                className="mt-2 rounded-card bg-primary px-4 py-2 font-medium text-white hover:bg-primary/90 disabled:opacity-60"
              >
                {t("common.save", lang)}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-8 rounded-card border border-primary/10 bg-surface p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="font-heading text-lg font-semibold text-ink">
              {t("patient.consultationsTitle", lang)}
            </h2>
            <button
              type="button"
              onClick={handleStartConsultation}
              disabled={starting}
              className="rounded-card bg-mint px-4 py-2 font-medium text-ink hover:bg-mint/90 disabled:opacity-60"
            >
              {t("patient.startNew", lang)}
            </button>
          </div>
          <ErrorText>{startError}</ErrorText>

          {consultations.length === 0 ? (
            <p className="mt-4 text-sm text-muted">{t("patient.noConsultations", lang)}</p>
          ) : (
            <ul className="mt-4 flex flex-col gap-3">
              {consultations.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/patient/consult/${c.id}`}
                    className="flex items-center justify-between rounded-card border border-primary/10 px-4 py-3 hover:border-primary/30"
                  >
                    <span className="text-sm text-ink">
                      {t("patient.startedOn", lang)}{" "}
                      {new Date(c.started_at).toLocaleDateString()}
                    </span>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_CLASSES[c.status] || ""}`}
                    >
                      {t(STATUS_KEYS[c.status] || "patient.statusInProgress", lang)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
