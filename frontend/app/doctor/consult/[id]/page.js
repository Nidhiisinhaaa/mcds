"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import DoctorLifestyleTable from "@/components/DoctorLifestyleTable";
import DoctorNotesBox from "@/components/DoctorNotesBox";
import DoctorTranscriptPanel from "@/components/DoctorTranscriptPanel";
import RecommendationList from "@/components/RecommendationList";
import RiskFlagList from "@/components/RiskFlagList";
import ScoreBreakdownChart from "@/components/ScoreBreakdownChart";
import StatusBadge from "@/components/StatusBadge";
import WellnessGauge from "@/components/WellnessGauge";
import {
  downloadConsultationReport,
  getDoctorConsultation,
  patchDoctorLifestyle,
  postDoctorNote,
  postDoctorReview,
} from "@/lib/api";
import { useRequireDoctor } from "@/lib/useRequireDoctor";

export default function DoctorConsultDetailPage() {
  const ready = useRequireDoctor();
  const { id } = useParams();

  const [consultation, setConsultation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingLifestyle, setSavingLifestyle] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!ready || !id) return;
    (async () => {
      const result = await getDoctorConsultation(id);
      if (result.ok) {
        setConsultation(result.data);
      } else {
        setError("Could not load this consultation.");
      }
      setLoading(false);
    })();
  }, [ready, id]);

  async function handleOverrideSave(overridesPayload) {
    setSavingLifestyle(true);
    const result = await patchDoctorLifestyle(id, overridesPayload);
    setSavingLifestyle(false);
    if (result.ok) {
      setConsultation(result.data);
    } else {
      setError("Could not save that change.");
    }
  }

  async function handleAddNote(text) {
    setSavingNote(true);
    const result = await postDoctorNote(id, text);
    setSavingNote(false);
    if (result.ok) {
      setConsultation((c) => ({ ...c, doctor_notes: [...(c.doctor_notes || []), result.data] }));
    } else {
      setError("Could not save that note.");
    }
  }

  async function handleMarkReviewed() {
    setReviewing(true);
    const result = await postDoctorReview(id);
    setReviewing(false);
    if (result.ok) {
      setConsultation(result.data);
    } else {
      setError("Could not mark this reviewed.");
    }
  }

  async function handleDownloadPdf() {
    setDownloading(true);
    try {
      await downloadConsultationReport(id);
    } catch {
      setError("Could not download the report.");
    } finally {
      setDownloading(false);
    }
  }

  if (loading || !ready) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-muted">Loading...</p>
      </main>
    );
  }

  if (!consultation) {
    return (
      <main className="flex flex-1 items-center justify-center px-6">
        <p className="text-danger">{error || "Consultation not found."}</p>
      </main>
    );
  }

  const patientProfile = consultation.patient_profile;
  const wellnessScore = consultation.wellness_score;

  return (
    <main className="flex-1 bg-page">
      <header className="border-b border-primary/10 bg-surface">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <Link href="/doctor" className="text-sm text-muted hover:text-primary">
              &larr; Back to queue
            </Link>
            <h1 className="mt-1 font-heading text-xl font-semibold text-ink">
              {patientProfile?.full_name || "Patient"}
              {patientProfile?.age && <span className="text-muted"> &middot; {patientProfile.age} yrs</span>}
              {patientProfile?.sex && <span className="text-muted"> &middot; {patientProfile.sex}</span>}
              {patientProfile?.bmi && <span className="text-muted"> &middot; BMI {patientProfile.bmi}</span>}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={consultation.status} />
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={downloading}
              className="rounded-card border border-primary/30 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/5 disabled:opacity-60"
            >
              {downloading ? "Preparing..." : "Download PDF"}
            </button>
            <button
              type="button"
              onClick={handleMarkReviewed}
              disabled={reviewing || consultation.status === "reviewed"}
              className="rounded-card bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
            >
              {consultation.status === "reviewed" ? "Reviewed" : reviewing ? "Saving..." : "Mark reviewed"}
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="mx-auto mt-4 max-w-6xl px-6">
          <p className="rounded-card border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
            {error}
          </p>
        </div>
      )}

      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 py-6 lg:grid-cols-2">
        {/* Left column */}
        <div className="flex flex-col gap-6">
          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <h2 className="font-heading text-base font-semibold text-ink">Clinical summary</h2>
            <p className="mt-2 text-sm text-ink">
              {consultation.chief_complaint_english || "No chief complaint recorded."}
            </p>
            {consultation.symptoms?.length > 0 && (
              <p className="mt-1 text-xs text-muted">
                {consultation.symptoms
                  .map((s) => `${s.name}${s.duration_text ? ` (${s.duration_text})` : ""}`)
                  .join(", ")}
              </p>
            )}
          </section>

          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <h2 className="font-heading text-base font-semibold text-ink">Lifestyle</h2>
            <p className="mt-1 text-xs text-muted">Hover a value to see the patient&apos;s own words.</p>
            <div className="mt-3">
              <DoctorLifestyleTable
                lifestyleProfile={consultation.lifestyle_profile}
                slotStatus={consultation.slot_status}
                onSave={handleOverrideSave}
                saving={savingLifestyle}
              />
            </div>
          </section>

          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <h2 className="font-heading text-base font-semibold text-ink">Risk flags</h2>
            <div className="mt-3">
              <RiskFlagList flags={consultation.risk_flags} />
            </div>
          </section>

          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <h2 className="font-heading text-base font-semibold text-ink">Recommendations</h2>
            <div className="mt-3">
              <RecommendationList
                recommendations={consultation.recommendations}
                isEscalated={consultation.status === "escalated"}
              />
            </div>
          </section>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-6">
          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <h2 className="font-heading text-base font-semibold text-ink">Lifestyle wellness score</h2>
            {wellnessScore ? (
              <>
                <div className="mt-3 flex justify-center">
                  <WellnessGauge total={wellnessScore.total} band={wellnessScore.band} />
                </div>
                <ScoreBreakdownChart breakdown={wellnessScore.breakdown} />
              </>
            ) : consultation.status === "completed" || consultation.status === "reviewed" ? (
              <p className="mt-3 text-sm text-muted">Not scored — insufficient responses.</p>
            ) : (
              <p className="mt-3 text-sm text-muted">Score not yet available.</p>
            )}
          </section>

          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <DoctorTranscriptPanel messages={consultation.messages} />
          </section>

          <section className="rounded-card border border-primary/10 bg-surface p-5">
            <DoctorNotesBox notes={consultation.doctor_notes} onAdd={handleAddNote} saving={savingNote} />
          </section>
        </div>
      </div>
    </main>
  );
}
