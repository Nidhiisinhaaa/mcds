"use client";

import { useState } from "react";

export default function DoctorTranscriptPanel({ messages }) {
  const [showEnglish, setShowEnglish] = useState(false);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-heading text-sm font-semibold text-ink">Transcript</h3>
        <div className="flex rounded-full border border-primary/20 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setShowEnglish(false)}
            className={`rounded-full px-3 py-1 ${!showEnglish ? "bg-primary text-white" : "text-muted"}`}
          >
            Original
          </button>
          <button
            type="button"
            onClick={() => setShowEnglish(true)}
            className={`rounded-full px-3 py-1 ${showEnglish ? "bg-primary text-white" : "text-muted"}`}
          >
            English
          </button>
        </div>
      </div>
      <div className="flex max-h-96 flex-col gap-3 overflow-y-auto rounded-card border border-primary/10 bg-page p-3">
        {(!messages || messages.length === 0) && <p className="text-sm text-muted">No messages yet.</p>}
        {messages?.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === "patient" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-card px-3 py-2 text-sm ${
                message.sender === "patient"
                  ? "bg-primary text-white"
                  : "border border-primary/10 bg-surface text-ink"
              }`}
            >
              <p>{showEnglish ? message.text_english : message.text_original}</p>
              {message.audio && <audio controls src={message.audio} className="mt-1.5 h-8 w-full" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
