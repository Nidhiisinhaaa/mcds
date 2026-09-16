import { t } from "@/lib/i18n";

export default function LanguagePill({ language }) {
  return (
    <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
      {t(`languages.${language}`, "en")}
    </span>
  );
}
