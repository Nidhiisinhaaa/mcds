import { t } from "@/lib/i18n";

export default function EscalationBanner({ text, lang = "en" }) {
  return (
    <div className="w-full rounded-card border-2 border-danger bg-danger/10 p-4">
      <p className="font-heading text-sm font-semibold text-danger">
        {t("consult.escalatedTitle", lang)}
      </p>
      {text && <p className="mt-1 text-sm text-danger">{text}</p>}
      <p className="mt-2 text-xs font-medium text-danger/80">
        {t("consult.escalatedFooter", lang)}
      </p>
    </div>
  );
}
