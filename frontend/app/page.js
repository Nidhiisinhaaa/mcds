import Link from "next/link";
import StepFlow from "@/components/StepFlow";
import { t } from "@/lib/i18n";

export default function LandingPage() {
  const steps = [1, 2, 3, 4, 5].map((n) => ({
    title: t(`landing.step${n}Title`, "en"),
    body: t(`landing.step${n}Body`, "en"),
  }));

  return (
    <main className="flex-1">
      <header className="border-b border-primary/10 bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <span className="font-heading text-lg font-semibold text-ink">
            {t("common.appName", "en")}
          </span>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/login" className="text-ink hover:text-primary">
              {t("auth.goToLogin", "en")}
            </Link>
            <Link
              href="/register"
              className="rounded-card bg-primary px-4 py-2 font-medium text-white hover:bg-primary/90"
            >
              {t("landing.ctaPrimary", "en")}
            </Link>
          </nav>
        </div>
      </header>

      <section className="bg-ink">
        <div className="mx-auto max-w-5xl px-6 py-20">
          <p className="text-sm font-medium tracking-wide text-mint uppercase">
            {t("landing.kicker", "en")}
          </p>
          <h1 className="mt-4 max-w-2xl font-heading text-4xl font-bold text-white sm:text-5xl">
            {t("landing.title", "en")}
          </h1>
          <p className="mt-6 max-w-xl text-base text-white/75">{t("landing.subtitle", "en")}</p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href="/register"
              className="rounded-card bg-mint px-6 py-3 font-medium text-ink hover:bg-mint/90"
            >
              {t("landing.ctaPrimary", "en")}
            </Link>
            <Link
              href="/login"
              className="rounded-card border border-white/30 px-6 py-3 font-medium text-white hover:bg-white/10"
            >
              {t("landing.ctaSecondary", "en")}
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-16">
        <h2 className="font-heading text-2xl font-semibold text-ink">
          {t("landing.stepsTitle", "en")}
        </h2>
        <div className="mt-8">
          <StepFlow steps={steps} />
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-20">
        <div className="rounded-card border border-warning/30 bg-warning/5 p-6">
          <h3 className="font-heading text-base font-semibold text-ink">
            {t("landing.disclaimerTitle", "en")}
          </h3>
          <p className="mt-2 text-sm text-muted">{t("landing.disclaimer", "en")}</p>
        </div>
      </section>
    </main>
  );
}
