"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { NotificationBell } from "@/components/NotificationBell";
import { GlobalSearchModal } from "@/components/GlobalSearchModal";
import { PilotFeedbackModal } from "@/components/PilotFeedbackModal";
import { useI18n, SUPPORTED_LOCALES, SupportedLocale } from "@/providers/I18nProvider";
import { SearchIcon } from "@/components/ui/Icons";
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
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);

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

  // Generate contextual breadcrumbs with plain human language (Section 8)
  const getBreadcrumbs = () => {
    if (pathname === "/dashboard") {
      return [{ label: "Home", href: "/dashboard" }];
    }
    if (pathname.startsWith("/cases/")) {
      const parts = pathname.split("/");
      if (parts[2] === "new") {
        return [
          { label: "My Case", href: "/cases" },
          { label: "Start a New Case", href: "/cases/new" },
        ];
      }
      return [
        { label: "My Case", href: "/cases" },
        { label: `Case #${parts[2].slice(0, 8).toUpperCase()}`, href: `/cases/${parts[2]}` },
      ];
    }
    if (pathname === "/cases") {
      return [{ label: "My Case", href: "/cases" }];
    }
    if (pathname.startsWith("/court-tracking")) {
      return [{ label: "Court / Location", href: "/court-tracking" }];
    }
    if (pathname.startsWith("/calendar")) {
      return [{ label: "Hearings", href: "/calendar" }];
    }
    if (pathname.startsWith("/documents")) {
      return [{ label: "My Documents", href: "/documents" }];
    }
    if (pathname.startsWith("/messages")) {
      return [{ label: "Talk to My Lawyer", href: "/messages" }];
    }
    if (pathname.startsWith("/lawyer/dashboard")) {
      return [{ label: "Practice Hub", href: "/lawyer/dashboard" }];
    }
    if (pathname.startsWith("/settings") || pathname.startsWith("/profile")) {
      return [{ label: "Settings", href: "/settings" }];
    }
    if (pathname.startsWith("/admin/dashboard")) {
      return [{ label: "Admin", href: "/admin/dashboard" }];
    }
    if (pathname.startsWith("/lawyers")) {
      return [{ label: "Find a Lawyer", href: "/lawyers" }];
    }
    return [{ label: "LCC", href: "/dashboard" }];
  };

  const breadcrumbs = getBreadcrumbs();

  const role = user?.role;
  const roleStyle =
    role === "ADMIN"
      ? { bg: "rgba(220, 38, 38, 0.08)", text: "#DC2626", border: "1px solid rgba(220, 38, 38, 0.2)" }
      : role === "LAWYER"
      ? { bg: "rgba(15, 30, 54, 0.08)", text: "#0F1E36", border: "1px solid rgba(15, 30, 54, 0.2)" }
      : { bg: "rgba(5, 150, 105, 0.08)", text: "#047857", border: "1px solid rgba(5, 150, 105, 0.2)" };

  return (
    <>
      <header className={styles.topBar}>
        <div className={styles.leftSection}>
          <button
            onClick={onOpenMobile}
            className={styles.mobileMenuBtn}
            aria-label="Open navigation menu"
          >
            ☰
          </button>

          {/* Contextual Breadcrumbs */}
          <nav className={styles.breadcrumbs} aria-label="Breadcrumbs">
            {breadcrumbs.map((crumb, idx) => {
              const isLast = idx === breadcrumbs.length - 1;
              return (
                <span key={idx} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  {idx > 0 && <span className={styles.breadcrumbSeparator}>/</span>}
                  {isLast ? (
                    <span className={styles.breadcrumbActive}>{crumb.label}</span>
                  ) : (
                    <Link href={crumb.href} className={styles.breadcrumbLink}>
                      {crumb.label}
                    </Link>
                  )}
                </span>
              );
            })}
          </nav>
        </div>

        <div className={styles.rightSection}>
          {/* Quick Search Button */}
          <button
            onClick={() => setSearchModalOpen(true)}
            className={styles.searchTriggerBtn}
            title="Search your cases and documents (Ctrl+K)"
          >
            <SearchIcon size={14} />
            <span className={styles.searchLabel}>Search...</span>
            <kbd className={styles.searchTriggerKbd}>Ctrl K</kbd>
          </button>

          {/* Indian Standard Time Indicator */}
          {istTime && (
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                padding: "3px 8px",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
                fontWeight: 500,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
              title="Official Indian Standard Time (IST) for court listings and hearings"
            >
              <span>🕒</span>
              <span>{istTime} IST</span>
            </span>
          )}

          {/* Language Selector */}
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as SupportedLocale)}
            aria-label="Choose Language"
            style={{
              padding: "4px 8px",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle)",
              background: "#FFFFFF",
              color: "var(--text-secondary)",
              fontSize: "12px",
              fontWeight: 500,
            }}
          >
            {SUPPORTED_LOCALES.map((loc) => (
              <option key={loc.code} value={loc.code}>
                {loc.nativeName}
              </option>
            ))}
          </select>

          {/* Notifications */}
          <NotificationBell />

          {/* Role Pill */}
          <span
            className={styles.roleBadge}
            style={{
              background: roleStyle.bg,
              color: roleStyle.text,
              border: roleStyle.border,
            }}
          >
            {role === "LAWYER" ? "Advocate" : role === "ADMIN" ? "Admin" : "Client"}
          </span>

          {/* Sign Out Button */}
          <button onClick={handleLogout} className={styles.logoutBtn}>
            Sign Out
          </button>
        </div>
      </header>

      {/* Global Search & Feedback Modals */}
      <GlobalSearchModal
        isOpen={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
      />
      <PilotFeedbackModal
        isOpen={feedbackModalOpen}
        onClose={() => setFeedbackModalOpen(false)}
      />
    </>
  );
}
