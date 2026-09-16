"use client";

import { useState } from "react";

export default function DoctorNotesBox({ notes, onAdd, saving }) {
  const [text, setText] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!text.trim()) return;
    await onAdd(text.trim());
    setText("");
  }

  return (
    <div>
      <h3 className="font-heading text-sm font-semibold text-ink">Doctor notes</h3>
      <div className="mt-2 flex max-h-48 flex-col gap-2 overflow-y-auto">
        {(!notes || notes.length === 0) && <p className="text-sm text-muted">No notes yet.</p>}
        {notes?.map((note) => (
          <div key={note.id} className="rounded-card border border-primary/10 bg-page p-2.5 text-sm">
            <p className="text-ink">{note.text}</p>
            <p className="mt-1 text-[11px] text-muted">
              Dr. {note.doctor_username} &middot; {new Date(note.created_at).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Add a note..."
          className="flex-1 resize-none rounded-card border border-muted/30 bg-surface px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        <button
          type="submit"
          disabled={saving || !text.trim()}
          className="self-end rounded-card bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          Add
        </button>
      </form>
    </div>
  );
}
