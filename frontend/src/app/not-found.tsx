"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EmptyState } from "@/components/ui/EmptyState";

export default function NotFound() {
  const router = useRouter();

  return (
    <main
      style={{
        minHeight: "75vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 20px",
      }}
      role="main"
      aria-label="Page Not Found"
    >
      <div style={{ maxWidth: "560px", width: "100%" }}>
        <EmptyState
          icon="⚖"
          title="Page Not Found"
          description="The court record, document, or workspace view you requested could not be located. It may have been relocated, archived, or you may need to verify the URL."
          actionLabel="Return to Dashboard"
          onAction={() => router.push("/dashboard")}
          secondaryActionLabel="Search Cases"
          onSecondaryAction={() => router.push("/cases")}
        />
        <div style={{ textAlign: "center", marginTop: "24px" }}>
          <Link
            href="/"
            style={{
              color: "var(--brand-primary, #818cf8)",
              fontSize: "13px",
              textDecoration: "none",
              fontWeight: 500,
            }}
          >
            ← Back to Legal Case Companion Home
          </Link>
        </div>
      </div>
    </main>
  );
}
