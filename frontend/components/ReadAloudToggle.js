"use client";

import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";

function findVoice(langCode) {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang?.toLowerCase().startsWith(langCode.toLowerCase())) || null;
}

/** Hidden entirely if no installed voice matches the message's language. */
export default function ReadAloudToggle({ text, language, uiLang = "en" }) {
  const [voice, setVoice] = useState(null);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    function updateVoice() {
      setVoice(findVoice(language));
    }
    updateVoice();
    window.speechSynthesis.addEventListener("voiceschanged", updateVoice);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", updateVoice);
  }, [language]);

  useEffect(
    () => () => {
      if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    },
    []
  );

  if (!voice || !text) return null;

  function toggle() {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
    >
      <SpeakerIcon active={speaking} />
      {t("consult.readAloud", uiLang)}
    </button>
  );
}

function SpeakerIcon({ active }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={`h-4 w-4 ${active ? "text-mint" : ""}`}
    >
      <path d="M4 9v6h4l5 4V5L8 9H4Z" />
      <path d="M16.5 8.5a5 5 0 0 1 0 7" strokeLinecap="round" />
    </svg>
  );
}
