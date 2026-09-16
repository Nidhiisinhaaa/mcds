/** DRF error responses are either {detail: "..."} or {field: ["msg", ...]}.
 * Pull out a single human-readable line for display. */
export function firstErrorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  for (const value of Object.values(data)) {
    if (Array.isArray(value) && value.length > 0) return String(value[0]);
    if (typeof value === "string") return value;
  }
  return fallback;
}
