"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { NotificationBell } from "@/components/NotificationBell";
import { GlobalSearchModal } from "@/components/GlobalSearchModal";
import { PilotFeedbackModal } from "@/components/PilotFeedbackModal";
import { useI18n, SUPPORTED_LOCALES, SupportedLocale } from "@/providers/I18nProvider";
import styles from "./TopBar.module.css";

interface TopBarProps {
  onOpenMobile: () => void;
}

export function TopBar({ onOpenMobile }: TopBarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { locale, setLocale } = useI18n();
  const router = useRouter();

  const [istTime, setIstTime] = useState("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const timeString = now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      });
      setIstTime(timeString);
    };
    updateTime();
    const interval = setInterval(updateTime, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  // Generate contextual breadcrumbs
  const getBreadcrumbs = () => {
    if (pathname === "/dashboard") {
      return [{ label: "Command Center", href: "/dashboard" }];
    }
    if (pathname.startsWith("/cases/")) {
      const parts = pathname.split("/");
      if (parts[2] === "new") {
        return [
          { label: "Matters", href: "/dashboard" },
          { label: "New Case Record", href: "/cases/new" },
        ];
      }
      return [
        { label: "Matters", href: "/dashboard" },
        { label: `Case #${parts[2].slice(0, 8).toUpperCase()}`, href: `/cases/${parts[2]}` },
      ];
    }
    if (pathname.startsWith("/court-tracking")) {
      return [{ label: "Court Case Tracking", href: "/court-tracking" }];
    }
    if (pathname.startsWith("/calendar")) {
      return [{ label: "Hearing Calendar", href: "/calendar" }];
    }
    if (pathname.startsWith("/documents")) {
      return [{ label: "Evidence & Documents", href: "/documents" }];
    }
    if (pathname.startsWith("/lawyer/dashboard")) {
      return [{ label: "Lawyer Practice Hub", href: "/lawyer/dashboard" }];
    }
    if (pathname.startsWith("/lawyer/profile")) {
      return [
        { label: "Lawyer Practice Hub", href: "/lawyer/dashboard" },
        { label: "Profile & Availability", href: "/lawyer/profile" },
      ];
    }
    if (pathname.startsWith("/settings") || pathname.startsWith("/profile")) {
      return [{ label: "Account & Settings", href: "/settings" }];
    }
    if (pathname.startsWith("/admin/dashboard")) {
      return [{ label: "Admin Console", href: "/admin/dashboard" }];
    }
    if (pathname.startsWith("/lawyers")) {
      return [{ label: "Counsel Directory", href: "/lawyers" }];
    }
    return [{ label: "Legal Case Companion", href: "/dashboard" }];
  };

  const breadcrumbs = getBreadcrumbs();

  const role = user?.role;
  const roleStyle =
    role === "ADMIN"
      ? { bg: "rgba(239, 68, 68, 0.15)", text: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.3)" }
      : role === "LAWYER"
      ? { bg: "rgba(109, 124, 255, 0.15)", text: "#8d98ff", border: "1px solid rgba(109, 124, 255, 0.3)" }
      : role === "CLIENT"
      ? { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa", border: "1px solid rgba(59, 130, 246, 0.3)" }
      : { bg: "transparent", text: "transparent", border: "none" };

  const [searchOpen, setSearchOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  return (
    <>
      <GlobalSearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
      <PilotFeedbackModal isOpen={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
      <header className={styles.topBar}>
        <div className={styles.leftSection}>
          <button
            onClick={onOpenMobile}
            className={styles.mobileMenuBtn}
            aria-label="Open navigation menu"
          >
            ☰
          </button>

          <nav className={styles.breadcrumbs}>
            {breadcrumbs.map((crumb, idx) => (
              <span key={idx} style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                {idx > 0 && <span className={styles.breadcrumbSeparator}>/</span>}
                {idx === breadcrumbs.length - 1 ? (
                  <span className={styles.breadcrumbActive}>{crumb.label}</span>
                ) : (
                  <Link href={crumb.href} className={styles.breadcrumbLink}>
                    {crumb.label}
                  </Link>
                )}
              </span>
            ))}
          </nav>
        </div>

        <div className={styles.rightSection}>
          {istTime && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-secondary, #94a3b8)",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: "6px",
                padding: "3px 8px",
              }}
              className={styles.desktopOnly}
              title="Indian Standard Time (IST) - Court sessions typically active 10:30 AM to 4:30 PM"
            >
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981" }} />
              <span>{istTime} IST</span>
            </div>
          )}

          {/* Language Selector */}
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as SupportedLocale)}
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "6px",
              color: "var(--text-secondary, #cbd5e1)",
              fontSize: "12px",
              fontWeight: 500,
              padding: "4px 8px",
              cursor: "pointer",
            }}
            aria-label="Select platform language"
          >
            {SUPPORTED_LOCALES.map((l) => (
              <option key={l.code} value={l.code} style={{ background: "#0e121a", color: "#ffffff" }}>
                {l.nativeName} ({l.name})
              </option>
            ))}
          </select>

          <button
            onClick={() => setSearchOpen(true)}
            className={styles.searchTriggerBtn}
            title="Search matters, documents, or legal counsel (Ctrl+K)"
          >
            <span>🔍</span>
            <span style={{ display: "inline-block" }}>Search...</span>
            <kbd className={styles.searchTriggerKbd}>⌘K</kbd>
          </button>

          <button
            onClick={() => setFeedbackOpen(true)}
            style={{
              padding: "4px 10px",
              background: "rgba(245, 158, 11, 0.12)",
              border: "1px solid rgba(245, 158, 11, 0.3)",
              borderRadius: "6px",
              color: "#f59e0b",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
            title="Share pilot feedback, friction, or report an issue"
          >
            <span>💬</span>
            <span className={styles.desktopOnly}>Feedback</span>
          </button>

          <NotificationBell />

          {role && (
            <span
              className={styles.roleBadge}
              style={{
                background: roleStyle.bg,
                color: roleStyle.text,
                border: roleStyle.border,
              }}
            >
              {role}
            </span>
          )}

          <button onClick={handleLogout} className={styles.logoutBtn}>
            Sign Out
          </button>
        </div>
      </header>
    </>
  );
}
