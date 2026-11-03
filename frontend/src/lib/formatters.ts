/**
 * Canonical Formatters for Legal Case Companion (LCC)
 * Provides consistent, localized (en-IN), and error-resilient formatting
 * for dates, times, relative timestamps, and monetary amounts.
 */

export interface DateFormatOptions {
  timeZone?: string;
  includeYear?: boolean;
}

/**
 * Formats an ISO 8601 date string to Indian standard date representation (e.g. "14 Oct 2026").
 */
export function formatDate(dateString?: string | null, options?: DateFormatOptions): string {
  if (!dateString) return "Not available";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Not available";
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: options?.includeYear !== false ? "numeric" : undefined,
      timeZone: options?.timeZone,
    });
  } catch {
    return "Not available";
  }
}

/**
 * Formats an ISO 8601 date string to Indian date and time (e.g. "14 Oct · 10:30 am").
 */
export function formatDateTime(dateString?: string | null, options?: DateFormatOptions): string {
  if (!dateString) return "Not available";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Not available";
    const datePart = d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: options?.includeYear ? "numeric" : undefined,
      timeZone: options?.timeZone,
    });
    const timePart = d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
      timeZone: options?.timeZone,
    });
    return `${datePart} · ${timePart}`;
  } catch {
    return "Not available";
  }
}

/**
 * Formats a timestamp into human-readable relative time (e.g., "5 mins ago", "yesterday", "in 2 days").
 */
export function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "Not available";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Not available";

    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSec < 45) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;

    return formatDate(dateString);
  } catch {
    return "Not available";
  }
}

/**
 * Formats a monetary number into Indian Rupee (INR) currency string (e.g. "₹1,500").
 */
export function formatCurrencyINR(amount?: number | null): string {
  if (amount === undefined || amount === null || isNaN(amount)) return "₹0";
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `₹${amount}`;
  }
}
