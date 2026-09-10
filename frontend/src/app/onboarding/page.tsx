"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";

export default function OnboardingRouter() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (loading) return;

    if (!user) {
      router.replace("/login");
      return;
    }

    if (user.role === "LAWYER") {
      router.replace("/onboarding/advocate");
    } else {
      router.replace("/onboarding/client");
    }
  }, [user, loading, router]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--surface-primary, #090d16)",
        color: "var(--text-secondary, #94a3b8)",
        fontSize: "14px",
      }}
    >
      Redirecting to your tailored workspace onboarding...
    </div>
  );
}
