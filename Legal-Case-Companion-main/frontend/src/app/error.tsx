"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/ui/ErrorState";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log non-sensitive diagnostic details internally
    console.error("Root error boundary caught:", error);
  }, [error]);

  return (
    <div
      style={{
        maxWidth: "1280px",
        margin: "0 auto",
        padding: "60px 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
      }}
    >
      <ErrorState
        title="Something went wrong while loading this information."
        description="We encountered an issue retrieving the latest data for this section. Please try again or return to the main overview."
        onRetry={reset}
        technicalError={
          process.env.NODE_ENV === "development" || error?.digest
            ? `${error.name}: ${error.message}${error.digest ? ` (Digest: ${error.digest})` : ""}`
            : undefined
        }
      />
    </div>
  );
}
