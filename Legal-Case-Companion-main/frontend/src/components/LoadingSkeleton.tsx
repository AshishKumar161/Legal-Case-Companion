import React from "react";

interface SkeletonProps {
  type?: "card" | "table-row" | "text-line" | "chat-bubble";
  count?: number;
}

export function LoadingSkeleton({ type = "card", count = 1 }: SkeletonProps) {
  const items = Array.from({ length: count });

  if (type === "table-row") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {items.map((_, i) => (
          <div
            key={i}
            style={{
              height: "44px",
              borderRadius: "8px",
              background: "linear-gradient(90deg, #101218 25%, #181c26 50%, #101218 75%)",
              backgroundSize: "200% 100%",
              animation: "pulse 1.5s infinite ease-in-out",
            }}
          />
        ))}
        <style jsx>{`
          @keyframes pulse {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
        `}</style>
      </div>
    );
  }

  if (type === "card") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {items.map((_, i) => (
          <div
            key={i}
            style={{
              height: "110px",
              borderRadius: "12px",
              background: "linear-gradient(90deg, #101218 25%, #181c26 50%, #101218 75%)",
              backgroundSize: "200% 100%",
              animation: "pulse 1.5s infinite ease-in-out",
              border: "1px solid var(--border-subtle)",
            }}
          />
        ))}
        <style jsx>{`
          @keyframes pulse {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {items.map((_, i) => (
        <div
          key={i}
          style={{
            height: "18px",
            width: `${75 + (i % 3) * 10}%`,
            borderRadius: "4px",
            background: "#161922",
          }}
        />
      ))}
    </div>
  );
}
