"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import {
  HomeIcon,
  CaseIcon,
  DocumentIcon,
  ChatIcon,
  CalendarIcon,
  LawyerIcon,
  AssistantIcon,
  ShieldIcon,
  SettingsIcon,
  CourthouseIcon,
} from "@/components/ui/Icons";
import { BottomSheet } from "@/components/ui/BottomSheet";
import styles from "./MobileBottomNav.module.css";

export function MobileBottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const role = user?.role;

  // Don't render on public landing or auth pages
  if (pathname === "/" || pathname.startsWith("/login") || pathname.startsWith("/register")) {
    return null;
  }

  const isLawyer = role === "LAWYER";

  const lawyerTabs = [
    { label: "Practice", href: "/lawyer/dashboard", icon: <HomeIcon size={20} /> },
    { label: "Cases", href: "/cases", icon: <CaseIcon size={20} /> },
    { label: "Court", href: "/court-tracking", icon: <CourthouseIcon size={20} /> },
    { label: "Calendar", href: "/calendar", icon: <CalendarIcon size={20} /> },
    { label: "Messages", href: "/messages", icon: <ChatIcon size={20} /> },
  ];

  const citizenTabs = [
    { label: "Home", href: "/dashboard", icon: <HomeIcon size={20} /> },
    { label: "Cases", href: "/cases", icon: <CaseIcon size={20} /> },
    { label: "Documents", href: "/documents", icon: <DocumentIcon size={20} /> },
    { label: "Messages", href: "/messages", icon: <ChatIcon size={20} /> },
  ];

  if (isLawyer) {
    return (
      <nav className={styles.mobileBottomNav} aria-label="Mobile Navigation">
        {lawyerTabs.map((tab) => {
          const isActive =
            pathname === tab.href ||
            (tab.href !== "/lawyer/dashboard" && pathname.startsWith(tab.href));

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
            >
              <span className={styles.navIcon}>{tab.icon}</span>
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <>
      <nav className={styles.mobileBottomNav} aria-label="Mobile Navigation">
        {citizenTabs.map((tab) => {
          const isActive =
            pathname === tab.href ||
            (tab.href !== "/dashboard" && pathname.startsWith(tab.href));

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
            >
              <span className={styles.navIcon}>{tab.icon}</span>
              <span>{tab.label}</span>
            </Link>
          );
        })}

        {/* More Tab */}
        <button
          onClick={() => setMoreOpen(true)}
          className={`${styles.navItem} ${moreOpen ? styles.navItemActive : ""}`}
          style={{ background: "transparent", border: "none", cursor: "pointer" }}
          aria-label="More options"
        >
          <span className={styles.navIcon}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="1" />
              <circle cx="19" cy="12" r="1" />
              <circle cx="5" cy="12" r="1" />
            </svg>
          </span>
          <span>More</span>
        </button>
      </nav>

      {/* Bottom Sheet for Additional Citizen Features */}
      <BottomSheet isOpen={moreOpen} onClose={() => setMoreOpen(false)} title="Menu & Services">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "12px" }}>
          <Link
            href="/consultations"
            onClick={() => setMoreOpen(false)}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              padding: "14px",
              background: "var(--surface-base, #F7F9FC)",
              borderRadius: "12px",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              color: "var(--text-primary, #17212B)",
              textDecoration: "none",
            }}
          >
            <CalendarIcon size={22} color="var(--navy-primary, #17324D)" />
            <span style={{ fontWeight: 600, fontSize: "14px" }}>Appointments</span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary, #52606D)" }}>
              Hearings & consultations
            </span>
          </Link>

          <Link
            href="/lawyers"
            onClick={() => setMoreOpen(false)}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              padding: "14px",
              background: "var(--surface-base, #F7F9FC)",
              borderRadius: "12px",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              color: "var(--text-primary, #17212B)",
              textDecoration: "none",
            }}
          >
            <LawyerIcon size={22} color="var(--navy-primary, #17324D)" />
            <span style={{ fontWeight: 600, fontSize: "14px" }}>Talk to a Lawyer</span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary, #52606D)" }}>
              Verified advocates
            </span>
          </Link>

          <Link
            href="/ai-advisor"
            onClick={() => setMoreOpen(false)}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              padding: "14px",
              background: "var(--surface-base, #F7F9FC)",
              borderRadius: "12px",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              color: "var(--text-primary, #17212B)",
              textDecoration: "none",
            }}
          >
            <AssistantIcon size={22} color="var(--navy-primary, #102A43)" />
            <span style={{ fontWeight: 600, fontSize: "14px" }}>Lex AI Advisor</span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary, #52606D)" }}>
              Plain answers about your case
            </span>
          </Link>

          <Link
            href="/support"
            onClick={() => setMoreOpen(false)}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              padding: "14px",
              background: "var(--surface-base, #F7F9FC)",
              borderRadius: "12px",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              color: "var(--text-primary, #17212B)",
              textDecoration: "none",
            }}
          >
            <ShieldIcon size={22} color="var(--teal-progress, #2F8F83)" />
            <span style={{ fontWeight: 600, fontSize: "14px" }}>Help & Guides</span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary, #52606D)" }}>
              Support and FAQs
            </span>
          </Link>

          <Link
            href="/profile"
            onClick={() => setMoreOpen(false)}
            style={{
              gridColumn: "span 2",
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "14px",
              background: "var(--surface-base, #F7F9FC)",
              borderRadius: "12px",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              color: "var(--text-primary, #17212B)",
              textDecoration: "none",
            }}
          >
            <SettingsIcon size={20} color="var(--text-muted, #7B8794)" />
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontWeight: 600, fontSize: "14px" }}>Account & Settings</span>
              <span style={{ fontSize: "12px", color: "var(--text-secondary, #52606D)" }}>
                {user?.full_name || user?.email}
              </span>
            </div>
          </Link>
        </div>
      </BottomSheet>
    </>
  );
}

