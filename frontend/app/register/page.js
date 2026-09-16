"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TextField, SelectField, ErrorText } from "@/components/FormField";
import { register, login } from "@/lib/api";
import { firstErrorMessage } from "@/lib/errors";
import { t } from "@/lib/i18n";

const PATIENT_LANGUAGES = ["en", "hi", "mr", "ta", "te", "bn", "kn", "gu", "ml"];

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    full_name: "",
    preferred_language: "en",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const result = await register(form);
    if (!result.ok) {
      setError(firstErrorMessage(result.data, t("common.genericError", "en")));
      setSubmitting(false);
      return;
    }

    const loginResult = await login({ username: form.username, password: form.password });
    setSubmitting(false);
    if (!loginResult.ok) {
      router.push("/login");
      return;
    }
    router.push("/consent");
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <div className="w-full max-w-md rounded-card border border-primary/10 bg-surface p-8">
        <h1 className="font-heading text-2xl font-semibold text-ink">
          {t("auth.registerTitle", "en")}
        </h1>
        <p className="mt-1 text-sm text-muted">{t("auth.registerSubtitle", "en")}</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <TextField
            id="full_name"
            label={t("auth.fullName", "en")}
            value={form.full_name}
            onChange={update("full_name")}
          />
          <TextField
            id="username"
            label={t("auth.username", "en")}
            value={form.username}
            onChange={update("username")}
            required
          />
          <TextField
            id="email"
            type="email"
            label={t("auth.email", "en")}
            value={form.email}
            onChange={update("email")}
          />
          <TextField
            id="password"
            type="password"
            label={t("auth.password", "en")}
            value={form.password}
            onChange={update("password")}
            required
          />
          <SelectField
            id="preferred_language"
            label={t("auth.preferredLanguage", "en")}
            value={form.preferred_language}
            onChange={update("preferred_language")}
          >
            {PATIENT_LANGUAGES.map((code) => (
              <option key={code} value={code}>
                {t(`languages.${code}`, "en")}
              </option>
            ))}
          </SelectField>

          <ErrorText>{error}</ErrorText>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-card bg-primary px-4 py-2.5 font-medium text-white hover:bg-primary/90 disabled:opacity-60"
          >
            {t("auth.submitRegister", "en")}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          {t("auth.haveAccount", "en")}{" "}
          <Link href="/login" className="text-primary hover:underline">
            {t("auth.goToLogin", "en")}
          </Link>
        </p>
      </div>
    </main>
  );
}
