"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorText } from "@/components/FormField";
import { postConsent } from "@/lib/api";
import { firstErrorMessage } from "@/lib/errors";
import { t } from "@/lib/i18n";
import { useRequireAuth } from "@/lib/useRequireAuth";

export default function ConsentPage() {
  useRequireAuth();
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!agreed) return;
    setError("");
    setSubmitting(true);
    const result = await postConsent();
    setSubmitting(false);
    if (!result.ok) {
      setError(firstErrorMessage(result.data, t("common.genericError", "en")));
      return;
    }
    router.push("/patient");
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl rounded-card border border-primary/10 bg-surface p-8">
        <h1 className="font-heading text-2xl font-semibold text-ink">{t("consent.title", "en")}</h1>
        <p className="mt-1 text-sm text-muted">{t("consent.subtitle", "en")}</p>

        <div className="mt-6 flex flex-col gap-5">
          <ConsentSection
            title={t("consent.collectedTitle", "en")}
            body={t("consent.collectedBody", "en")}
          />
          <ConsentSection title={t("consent.doctorTitle", "en")} body={t("consent.doctorBody", "en")} />
          <ConsentSection
            title={t("consent.notDiagnosisTitle", "en")}
            body={t("consent.notDiagnosisBody", "en")}
          />
          <div className="rounded-card border border-danger/30 bg-danger/5 p-4">
            <h3 className="font-heading text-sm font-semibold text-danger">
              {t("consent.emergencyTitle", "en")}
            </h3>
            <p className="mt-1 text-sm text-danger/90">{t("consent.emergencyBody", "en")}</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4 border-t border-primary/10 pt-6">
          <label className="flex items-start gap-3 text-sm text-ink">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-muted/40 text-primary focus:ring-primary/30"
            />
            <span>{t("consent.checkboxLabel", "en")}</span>
          </label>

          <ErrorText>{error}</ErrorText>

          <button
            type="submit"
            disabled={!agreed || submitting}
            className="rounded-card bg-primary px-4 py-2.5 font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("consent.submit", "en")}
          </button>
        </form>
      </div>
    </main>
  );
}

function ConsentSection({ title, body }) {
  return (
    <div>
      <h3 className="font-heading text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-sm text-muted">{body}</p>
    </div>
  );
}
