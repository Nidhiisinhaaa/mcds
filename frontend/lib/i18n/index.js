import en from "./en.json";
import hi from "./hi.json";

// UI chrome only. The conversation itself always runs in the patient's
// chosen language regardless of what's listed here - the backend handles
// that translation. Any language not listed here falls back to English UI.
const DICTIONARIES = { en, hi };

export const SUPPORTED_UI_LANGUAGES = Object.keys(DICTIONARIES);

function lookup(dict, key) {
  return key
    .split(".")
    .reduce((obj, part) => (obj && typeof obj === "object" ? obj[part] : undefined), dict);
}

export function t(key, lang = "en") {
  const dict = DICTIONARIES[lang] || DICTIONARIES.en;
  const value = lookup(dict, key);
  if (value !== undefined) return value;
  const fallback = lookup(DICTIONARIES.en, key);
  return fallback !== undefined ? fallback : key;
}
