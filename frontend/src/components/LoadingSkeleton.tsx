"use client";

import React from "react";
import { Skeleton } from "./ui/Skeleton";

export interface LoadingSkeletonProps {
  type?: "card" | "table-row" | "text-line" | "chat-bubble";
  count?: number;
}

export function LoadingSkeleton({ type = "card", count = 1 }: LoadingSkeletonProps) {
  const mapVariant = (): "card" | "table-row" | "text" | "rectangular" => {
    switch (type) {
      case "table-row":
        return "table-row";
      case "card":
        return "card";
      case "chat-bubble":
        return "rectangular";
      case "text-line":
      default:
        return "text";
    }
  };

  return <Skeleton variant={mapVariant()} count={count} />;
}
