"use client";

import { useEffect, useRef, useState } from "react";
import { t } from "@/lib/i18n";

const MAX_SECONDS = 60;
const PREFERRED_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null; // no MediaRecorder support at all
  for (const type of PREFERRED_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return ""; // MediaRecorder exists but none of our preferred types do - use the browser default
}

/** Tap to record (max 60s, auto-stops), tap to stop early. Calls
 * onRecordingComplete(blob, filename) and awaits it while showing
 * "Transcribing...". */
export default function MicButton({ onRecordingComplete, disabled, lang = "en" }) {
  const [status, setStatus] = useState("idle"); // idle | recording | transcribing | denied | unsupported
  const [seconds, setSeconds] = useState(0);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    },
    []
  );

  function stopTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopRecording() {
    stopTimer();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
  }

  async function startRecording() {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setStatus("unsupported");
      return;
    }
    const mimeType = pickMimeType();
    if (mimeType === null) {
      setStatus("unsupported");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        stopTimer();
        stream.getTracks().forEach((track) => track.stop());
        const usedType = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: usedType });
        const extension = usedType.includes("mp4") ? "mp4" : "webm";
        setStatus("transcribing");
        try {
          await onRecordingComplete(blob, `recording.${extension}`);
        } finally {
          setStatus("idle");
          setSeconds(0);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setStatus("recording");
      setSeconds(0);
      timerRef.current = setInterval(() => {
        setSeconds((s) => {
          const next = s + 1;
          if (next >= MAX_SECONDS) {
            stopRecording();
            return MAX_SECONDS;
          }
          return next;
        });
      }, 1000);
    } catch (err) {
      setStatus(err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError" ? "denied" : "unsupported");
    }
  }

  function handleClick() {
    if (status === "recording") stopRecording();
    else if (status === "idle" || status === "denied") startRecording();
  }

  const isRecording = status === "recording";
  const isTranscribing = status === "transcribing";

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || isTranscribing || status === "unsupported"}
        aria-label={isRecording ? t("consult.micStop", lang) : t("consult.micStart", lang)}
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
          isRecording
            ? "animate-pulse border-danger bg-danger/10 text-danger"
            : "border-primary bg-primary text-white hover:bg-primary/90"
        } disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <MicIcon />
      </button>
      {isRecording && (
        <span className="text-xs tabular-nums text-muted">
          {seconds}s / {MAX_SECONDS}s
        </span>
      )}
      {isTranscribing && <span className="text-xs text-muted">{t("consult.transcribing", lang)}</span>}
      {status === "denied" && (
        <span className="max-w-[10rem] text-center text-xs text-warning">
          {t("consult.micDenied", lang)}
        </span>
      )}
      {status === "unsupported" && (
        <span className="max-w-[10rem] text-center text-xs text-muted">
          {t("consult.micUnsupported", lang)}
        </span>
      )}
    </div>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
      <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" />
      <path d="M19 11a7 7 0 0 1-14 0" strokeLinecap="round" />
      <path d="M12 18v3" strokeLinecap="round" />
    </svg>
  );
}
