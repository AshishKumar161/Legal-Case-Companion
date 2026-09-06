"use client";

import React, { useState } from "react";

export interface AvatarProps {
  name: string;
  src?: string;
  size?: "xs" | "sm" | "md" | "lg";
  roleBadge?: "client" | "lawyer" | "admin";
  className?: string;
  style?: React.CSSProperties;
}

export function Avatar({
  name,
  src,
  size = "md",
  roleBadge,
  className,
  style,
}: AvatarProps) {
  const [imageFailed, setImageFailed] = useState(false);

  // Compute initials (e.g. "Ananya Roy" -> "AR")
  const initials = name
    ? name
        .split(" ")
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "?";

  const sizePixels: Record<string, number> = {
    xs: 24,
    sm: 32,
    md: 40,
    lg: 52,
  };

  const px = sizePixels[size] || 40;
  const fontSize = px <= 24 ? "10px" : px <= 32 ? "12px" : px <= 40 ? "14px" : "18px";

  const roleColors: Record<string, string> = {
    lawyer: "var(--brand-primary, #6366f1)",
    client: "var(--success, #10B981)",
    admin: "var(--info, #06B6D4)",
  };

  return (
    <div
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: `${px}px`,
        height: `${px}px`,
        borderRadius: "50%",
        flexShrink: 0,
        ...style,
      }}
      className={className}
      aria-label={`Avatar for ${name}`}
    >
      {src && !imageFailed ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={src}
          alt={name}
          onError={() => setImageFailed(true)}
          style={{
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            objectFit: "cover",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
          }}
        />
      ) : (
        <div
          style={{
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            background: "linear-gradient(135deg, #151A24 0%, #1f273b 100%)",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.15))",
            color: "var(--text-primary, #f8fafc)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize,
            fontWeight: 700,
            fontFamily: "var(--font-sans, sans-serif)",
            userSelect: "none",
          }}
        >
          {initials}
        </div>
      )}

      {roleBadge && (
        <span
          title={`Role: ${roleBadge.toUpperCase()}`}
          style={{
            position: "absolute",
            bottom: "-1px",
            right: "-1px",
            width: `${Math.max(8, px * 0.28)}px`,
            height: `${Math.max(8, px * 0.28)}px`,
            borderRadius: "50%",
            backgroundColor: roleColors[roleBadge] || "#94a3b8",
            border: "2px solid var(--surface-base, #07090E)",
          }}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
