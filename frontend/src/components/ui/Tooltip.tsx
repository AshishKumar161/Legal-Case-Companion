"use client";

import React, { useState, useId } from "react";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  placement?: "top" | "bottom" | "left" | "right";
}

export function Tooltip({ content, children, placement = "top" }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const tooltipId = useId();

  if (!content) return children;

  const placementStyles: Record<string, React.CSSProperties> = {
    top: {
      bottom: "calc(100% + 6px)",
      left: "50%",
      transform: "translateX(-50%)",
    },
    bottom: {
      top: "calc(100% + 6px)",
      left: "50%",
      transform: "translateX(-50%)",
    },
    left: {
      right: "calc(100% + 6px)",
      top: "50%",
      transform: "translateY(-50%)",
    },
    right: {
      left: "calc(100% + 6px)",
      top: "50%",
      transform: "translateY(-50%)",
    },
  };

  return (
    <div
      style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setIsVisible(false);
        }
      }}
    >
      {React.cloneElement(children as React.ReactElement<any>, {
        "aria-describedby": isVisible ? tooltipId : undefined,
      })}

      {isVisible && (
        <div
          id={tooltipId}
          role="tooltip"
          style={{
            position: "absolute",
            background: "var(--surface-elevated, #151A24)",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
            color: "var(--text-primary, #f8fafc)",
            padding: "4px 8px",
            borderRadius: "var(--radius-xs, 4px)",
            fontSize: "var(--font-size-2xs, 11px)",
            lineHeight: 1.3,
            whiteSpace: "nowrap",
            zIndex: "var(--z-tooltip, 1700)",
            boxShadow: "var(--shadow-md)",
            pointerEvents: "none",
            ...placementStyles[placement],
          }}
        >
          {content}
        </div>
      )}
    </div>
  );
}
