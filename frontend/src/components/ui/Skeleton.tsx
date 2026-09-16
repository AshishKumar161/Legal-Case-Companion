"use client";

import React from "react";

export interface SkeletonProps {
  variant?: "text" | "circular" | "rectangular" | "card" | "table-row";
  width?: string | number;
  height?: string | number;
  count?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({
  variant = "text",
  width,
  height,
  count = 1,
  className,
  style,
}: SkeletonProps) {
  const items = Array.from({ length: count });

  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case "circular":
        return {
          borderRadius: "50%",
          width: width || "40px",
          height: height || "40px",
        };
      case "rectangular":
        return {
          borderRadius: "var(--radius-md, 8px)",
          width: width || "100%",
          height: height || "120px",
        };
      case "card":
        return {
          borderRadius: "var(--radius-lg, 12px)",
          width: width || "100%",
          height: height || "140px",
          border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.06))",
        };
      case "table-row":
        return {
          borderRadius: "var(--radius-sm, 6px)",
          width: width || "100%",
          height: height || "44px",
        };
      case "text":
      default:
        return {
          borderRadius: "var(--radius-xs, 4px)",
          width: width || "100%",
          height: height || "16px",
        };
    }
  };

  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading content..."
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        width: width && typeof width === "string" ? width : "100%",
        ...style,
      }}
      className={className}
    >
      {items.map((_, i) => (
        <div
          key={i}
          style={{
            background: "linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)",
            backgroundSize: "200% 100%",
            animation: "lccSkeletonPulse 1.6s ease-in-out infinite",
            ...getVariantStyles(),
          }}
        />
      ))}

      <style jsx>{`
        @keyframes lccSkeletonPulse {
          0% {
            background-position: 200% 0;
          }
          100% {
            background-position: -200% 0;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          div {
            animation: none !important;
            background: #e2e8f0 !important;
          }
        }
      `}</style>
    </div>
  );
}
