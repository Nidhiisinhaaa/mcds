"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TextField, ErrorText } from "@/components/FormField";
import { login, getMe, redirectPathForRole } from "@/lib/api";
import { firstErrorMessage } from "@/lib/errors";
import { t } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const result = await login(form);
    if (!result.ok) {
      setError(firstErrorMessage(result.data, t("common.genericError", "en")));
      setSubmitting(false);
      return;
    }

    const me = await getMe();
    setSubmitting(false);
    router.push(redirectPathForRole(me.data?.role));
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <div className="w-full max-w-md rounded-card border border-primary/10 bg-surface p-8">
        <h1 className="font-heading text-2xl font-semibold text-ink">
          {t("auth.loginTitle", "en")}
        </h1>
        <p className="mt-1 text-sm text-muted">{t("auth.loginSubtitle", "en")}</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <TextField
            id="username"
            label={t("auth.username", "en")}
            value={form.username}
            onChange={update("username")}
            required
          />
          <TextField
            id="password"
            type="password"
            label={t("auth.password", "en")}
            value={form.password}
            onChange={update("password")}
            required
          />

          <ErrorText>{error}</ErrorText>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-card bg-primary px-4 py-2.5 font-medium text-white hover:bg-primary/90 disabled:opacity-60"
          >
            {t("auth.submitLogin", "en")}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          {t("auth.noAccount", "en")}{" "}
          <Link href="/register" className="text-primary hover:underline">
            {t("auth.goToRegister", "en")}
          </Link>
        </p>
      </div>
    </main>
  );
}
