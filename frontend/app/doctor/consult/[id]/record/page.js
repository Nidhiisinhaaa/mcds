"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import ChatBubble from "@/components/ChatBubble";
import EscalationBanner from "@/components/EscalationBanner";
import LanguagePill from "@/components/LanguagePill";
import MicButton from "@/components/MicButton";
import ProgressChips from "@/components/ProgressChips";
import ReadAloudToggle from "@/components/ReadAloudToggle";
import {
  getConsultationState,
  getDoctorConsultation,
  postConsultationAudio,
  postConsultationText,
  postDoctorConsentConfirm,
} from "@/lib/api";
import { useRequireDoctor } from "@/lib/useRequireDoctor";

export default function DoctorRecordConsultationPage() {
  const ready = useRequireDoctor();
  const router = useRouter();
  const { id } = useParams();

  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [patientName, setPatientName] = useState("");
  const [language, setLanguage] = useState("en");
  const [status, setStatus] = useState("in_progress");
  const [messages, setMessages] = useState([]);
  const [slotStatus, setSlotStatus] = useState({});
  const [consentGivenAt, setConsentGivenAt] = useState(null);
  const [confirmingConsent, setConfirmingConsent] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);

  useEffect(() => {
    if (!ready || !id) return;
    (async () => {
      const [detail, state] = await Promise.all([
        getDoctorConsultation(id),
        getConsultationState(id),
      ]);
      if (!detail.ok) {
        setNotFound(true);
        setLoading(false);
        return;
      }
      setPatientName(detail.data.patient_profile?.full_name || "Patient");
      setLanguage(detail.data.language || "en");
      setStatus(detail.data.status);
      setMessages(detail.data.messages || []);
      setConsentGivenAt(detail.data.patient_profile?.consent_given_at || null);
      if (state.ok) setSlotStatus(state.data.slot_status || {});
      setLoading(false);
    })();
  }, [ready, id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  useEffect(() => {
    if (status === "completed") {
      router.replace(`/doctor/consult/${id}`);
    }
  }, [status, id, router]);

  async function handleConfirmConsent() {
    setConfirmingConsent(true);
    setError("");
    const result = await postDoctorConsentConfirm(id);
    setConfirmingConsent(false);
    if (!result.ok) {
      setError("Could not record consent. Please try again.");
      return;
    }
    setConsentGivenAt(result.data.consent_given_at);
  }

  function applyTurnResult(data) {
    setMessages((prev) => [...prev, data.patient_message, ...(data.ai_message ? [data.ai_message] : [])]);
    setSlotStatus(data.slot_status || {});
    setStatus(data.status);
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
      setError("Could not send that message. Please try again.");
      return;
    }
    setText("");
    applyTurnResult(result.data);
  }

  async function handleRecordingComplete(blob, filename) {
    setError("");
    const result = await postConsultationAudio(id, blob, filename);
    if (!result.ok) {
      setError("Could not send that recording. Please try again.");
    } else {
      applyTurnResult(result.data);
    }
  }

  if (loading || !ready) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-muted">Loading...</p>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="flex flex-1 items-center justify-center px-6">
        <p className="text-danger">
          Could not load this consultation. It may not exist, or may not be assigned to you.
        </p>
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
            <Link href="/doctor" className="text-sm text-muted hover:text-primary">
              &larr; Back to queue
            </Link>
            <div className="flex items-center gap-2">
              <LanguagePill language={language} />
              <Link
                href={`/doctor/consult/${id}`}
                className="text-sm text-primary hover:underline"
              >
                View clinical detail
              </Link>
            </div>
          </div>
          <div>
            <h1 className="font-heading text-lg font-semibold text-ink">{patientName}</h1>
            <p className="text-xs text-muted">Recording in-clinic consultation</p>
          </div>
          {consentGivenAt && <ProgressChips slotStatus={slotStatus} lang={language} />}
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-6">
        {!consentGivenAt ? (
          <section className="rounded-card border-2 border-warning bg-warning/5 p-6">
            <h2 className="font-heading text-base font-semibold text-ink">
              Confirm verbal consent
            </h2>
            <p className="mt-2 text-sm text-ink">
              This patient hasn&apos;t given consent through the app. Before recording this
              consultation, confirm that you obtained the patient&apos;s verbal consent in
              person. This will be recorded with a timestamp and your identity.
            </p>
            <button
              type="button"
              onClick={handleConfirmConsent}
              disabled={confirmingConsent}
              className="mt-4 rounded-card bg-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
            >
              {confirmingConsent ? "Recording..." : "I confirm verbal consent was obtained"}
            </button>
            {error && <p className="mt-2 text-sm text-danger">{error}</p>}
          </section>
        ) : (
          <>
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
                        uiLang="en"
                      />
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          </>
        )}
      </div>

      {consentGivenAt && status === "in_progress" && (
        <form
          onSubmit={handleSendText}
          className="border-t border-primary/10 bg-surface px-6 py-4"
        >
          <div className="mx-auto flex max-w-3xl items-end gap-3">
            <MicButton
              onRecordingComplete={handleRecordingComplete}
              disabled={inputDisabled}
              lang="en"
            />
            <textarea
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={inputDisabled}
              placeholder="Type what the patient said..."
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
              Send
            </button>
          </div>
          {error && <p className="mx-auto mt-2 max-w-3xl text-sm text-danger">{error}</p>}
        </form>
      )}
    </main>
  );
}
