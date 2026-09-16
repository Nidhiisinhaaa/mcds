"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ScoreBadge from "@/components/ScoreBadge";
import StatusBadge from "@/components/StatusBadge";
import { listDoctorConsultations, logout } from "@/lib/api";
import { useRequireDoctor } from "@/lib/useRequireDoctor";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "escalated", label: "Escalated" },
  { value: "completed", label: "Completed" },
  { value: "in_progress", label: "In progress" },
  { value: "reviewed", label: "Reviewed" },
];

export default function DoctorQueuePage() {
  const ready = useRequireDoctor();
  const router = useRouter();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      const result = await listDoctorConsultations({ status: statusFilter, q: search });
      if (cancelled) return;
      if (result.ok) {
        setRows(result.data.results || result.data || []);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, statusFilter, search]);

  if (!ready) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-muted">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex-1 bg-page">
      <header className="border-b border-primary/10 bg-surface">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <span className="font-heading text-lg font-semibold text-ink">Bedside &middot; Doctor</span>
          <button
            type="button"
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-sm text-muted hover:text-primary"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="font-heading text-2xl font-semibold text-ink">Patient queue</h1>
          <div className="flex flex-wrap gap-3">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search patient or complaint..."
              className="rounded-card border border-muted/30 bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-card border border-muted/30 bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6 overflow-x-auto rounded-card border border-primary/10 bg-surface">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-primary/10 text-left text-xs font-medium uppercase tracking-wide text-muted">
                <th className="px-4 py-3">Patient</th>
                <th className="px-4 py-3">Age</th>
                <th className="px-4 py-3">Language</th>
                <th className="px-4 py-3">Chief complaint</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Flags</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Started</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted">
                    Loading...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted">
                    No consultations found.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => router.push(`/doctor/consult/${row.id}`)}
                    className={`cursor-pointer border-b border-primary/5 last:border-0 hover:bg-page ${
                      row.status === "escalated" ? "bg-danger/5" : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-medium text-ink">
                      <Link href={`/doctor/consult/${row.id}`} onClick={(e) => e.stopPropagation()}>
                        {row.patient_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-ink">{row.patient_age ?? "-"}</td>
                    <td className="px-4 py-3 text-ink">{row.language}</td>
                    <td className="max-w-[260px] truncate px-4 py-3 text-ink" title={row.chief_complaint_english}>
                      {row.chief_complaint_english || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge total={row.wellness_total} band={row.wellness_band} status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-ink">{row.flag_count}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {new Date(row.started_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
