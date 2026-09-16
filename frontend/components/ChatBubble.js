"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";

export default function ChatBubble({ message, lang = "en" }) {
  const [showEnglish, setShowEnglish] = useState(false);
  const isPatient = message.sender === "patient";
  const canToggle =
    message.text_english && message.text_original && message.text_english !== message.text_original;

  return (
    <div className={`flex ${isPatient ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-card px-4 py-3 text-sm leading-relaxed ${
          isPatient ? "bg-primary text-white" : "bg-surface text-ink border border-primary/10"
        }`}
      >
        <p>{showEnglish ? message.text_english : message.text_original}</p>
        {canToggle && (
          <button
            type="button"
            onClick={() => setShowEnglish((v) => !v)}
            className={`mt-1.5 text-xs underline underline-offset-2 ${
              isPatient ? "text-white/80 hover:text-white" : "text-muted hover:text-primary"
            }`}
          >
            {t(showEnglish ? "common.hideEnglish" : "common.showEnglish", lang)}
          </button>
        )}
      </div>
    </div>
  );
}
