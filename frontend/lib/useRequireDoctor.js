"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, isAuthenticated } from "@/lib/api";

/** Redirects non-doctors away (to /login if unauthenticated, /patient if a
 * patient). Returns true once confirmed the current user is a doctor, so a
 * page can gate its own rendering until then. */
export function useRequireDoctor() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    (async () => {
      const result = await getMe();
      if (!result.ok || result.data?.role !== "doctor") {
        router.replace("/patient");
        return;
      }
      setReady(true);
    })();
  }, [router]);

  return ready;
}
