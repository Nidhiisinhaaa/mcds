"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ChatBubble from "@/components/ChatBubble";
import EscalationBanner from "@/components/EscalationBanner";
import LanguagePill from "@/components/LanguagePill";
import MicButton from "@/components/MicButton";
import ProgressChips from "@/components/ProgressChips";
import ReadAloudToggle from "@/components/ReadAloudToggle";
import WellnessGauge from "@/components/WellnessGauge";
import {
  getConsultation,
  getConsultationState,
  postConsultationAudio,
  postConsultationText,
} from "@/lib/api";
import { t } from "@/lib/i18n";
import { useRequireAuth } from "@/lib/useRequireAuth";

export default function ConsultPage() {
  useRequireAuth();
  const { id } = useParams();

  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [language, setLanguage] = useState("en");
  const [status, setStatus] = useState("in_progress");
  const [messages, setMessages] = useState([]);
  const [slotStatus, setSlotStatus] = useState({});
  const [wellnessScore, setWellnessScore] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);

  useEffect(() => {
    if (!id) return;
    (async () => {
      const [detail, state] = await Promise.all([getConsultation(id), getConsultationState(id)]);
      if (!detail.ok) {
        setNotFound(true);
        setLoading(false);
        return;
      }
      setLanguage(detail.data.language || "en");
      setStatus(detail.data.status);
      setMessages(detail.data.messages || []);
      setWellnessScore(detail.data.wellness_score);
      setRecommendations(detail.data.recommendations || []);
      if (state.ok) setSlotStatus(state.data.slot_status || {});
      setLoading(false);
    })();
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function refetchDetail() {
    const result = await getConsultation(id);
    if (result.ok) {
      setWellnessScore(result.data.wellness_score);
      setRecommendations(result.data.recommendations || []);
    }
  }

  function applyTurnResult(data) {
    setMessages((prev) => [...prev, data.patient_message, ...(data.ai_message ? [data.ai_message] : [])]);
    setSlotStatus(data.slot_status || {});
    setStatus(data.status);
    if (data.status === "completed") refetchDetail();
  }

  async function handleSendText(e) {
    e.preventDefault();
    const value = text.trim();
    if (!value || sending) return;
    setSending(true);
    setError("");
    const result = await postConsultationText(id, value);
    setSending(false);
    if (!result.ok) {
      setError(t("consult.sendingError", language));
      return;
    }
    setText("");
    applyTurnResult(result.data);
  }

  async function handleRecordingComplete(blob, filename) {
    setError("");
    const result = await postConsultationAudio(id, blob, filename);
    if (!result.ok) {
      setError(t("consult.sendingError", language));
    } else {
      applyTurnResult(result.data);
    }
  }

  if (loading) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-muted">{t("common.loading", "en")}</p>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="flex flex-1 items-center justify-center px-6">
        <p className="text-danger">{t("common.genericError", "en")}</p>
      </main>
    );
  }

  const inputDisabled = status !== "in_progress" || sending;
  const lastAiMessage = [...messages].reverse().find((m) => m.sender === "ai");

  return (
    <main className="flex flex-1 flex-col bg-page">
      <header className="border-b border-primary/10 bg-surface">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/patient" className="text-sm text-muted hover:text-primary">
              &larr; {t("consult.backToPatient", language)}
            </Link>
            <LanguagePill language={language} />
          </div>
          <ProgressChips slotStatus={slotStatus} lang={language} />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-6">
        {status === "escalated" && (
          <EscalationBanner text={lastAiMessage?.text_original} lang={language} />
        )}

        <div className="flex flex-1 flex-col gap-3">
          {messages.map((message) => (
            <div key={message.id} className="flex flex-col gap-1">
              <ChatBubble message={message} lang={language} />
              {message.sender === "ai" && (
                <div className="pl-1">
                  <ReadAloudToggle
                    text={message.text_original}
                    language={language}
                    uiLang={language}
                  />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {status === "completed" && (
          <section className="mt-4 rounded-card border border-primary/10 bg-surface p-6">
            <h2 className="font-heading text-xl font-semibold text-ink">
              {t("consult.completedTitle", language)}
            </h2>

            {wellnessScore && (
              <div className="mt-4 flex flex-col items-center gap-2 rounded-card bg-page p-4">
                <span className="text-xs font-medium uppercase tracking-wide text-muted">
                  {t("consult.wellnessScore", language)}
                </span>
                <WellnessGauge total={wellnessScore.total} band={wellnessScore.band} />
              </div>
            )}

            {recommendations.length > 0 && (
              <div className="mt-6">
                <h3 className="font-heading text-base font-semibold text-ink">
                  {t("consult.recommendationsTitle", language)}
                </h3>
                <ul className="mt-3 flex flex-col gap-2">
                  {recommendations.map((rec, index) => (
                    <li
                      key={index}
                      className="rounded-card border border-mint/30 bg-mint/5 px-4 py-3 text-sm text-ink"
                    >
                      {rec.text_patient_language}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="mt-6 text-sm font-medium text-primary">
              {t("consult.doctorWillReview", language)}
            </p>
          </section>
        )}
      </div>

      {status === "in_progress" && (
        <form
          onSubmit={handleSendText}
          className="border-t border-primary/10 bg-surface px-6 py-4"
        >
          <div className="mx-auto flex max-w-3xl items-end gap-3">
            <MicButton
              onRecordingComplete={handleRecordingComplete}
              disabled={inputDisabled}
              lang={language}
            />
            <textarea
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={inputDisabled}
              placeholder={t("consult.typePlaceholder", language)}
              className="flex-1 resize-none rounded-card border border-muted/30 bg-page px-3 py-2.5 text-sm text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendText(e);
                }
              }}
            />
            <button
              type="submit"
              disabled={inputDisabled || !text.trim()}
              className="rounded-card bg-primary px-4 py-2.5 font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t("consult.send", language)}
            </button>
          </div>
          {error && <p className="mx-auto mt-2 max-w-3xl text-sm text-danger">{error}</p>}
        </form>
      )}
    </main>
  );
}
