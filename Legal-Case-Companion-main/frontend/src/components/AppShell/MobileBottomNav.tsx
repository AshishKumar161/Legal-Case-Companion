"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import styles from "./MobileBottomNav.module.css";

export function MobileBottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role = user?.role;

  // Don't render on public landing or auth pages
  if (pathname === "/" || pathname.startsWith("/login") || pathname.startsWith("/register")) {
    return null;
  }

  const isLawyer = role === "LAWYER";

  const tabs = isLawyer
    ? [
        { label: "Overview", href: "/lawyer/dashboard", icon: "📈" },
        { label: "Matters", href: "/cases", icon: "⚖" },
        { label: "Court", href: "/court-tracking", icon: "🏛" },
        { label: "Calendar", href: "/calendar", icon: "📅" },
        { label: "Consults", href: "/consultations", icon: "📹" },
      ]
    : [
        { label: "Home", href: "/dashboard", icon: "📊" },
        { label: "Cases", href: "/cases", icon: "⚖" },
        { label: "Court", href: "/court-tracking", icon: "🏛" },
        { label: "Calendar", href: "/calendar", icon: "📅" },
        { label: "Find Help", href: "/lawyers", icon: "🔍" },
      ];

  return (
    <nav className={styles.mobileBottomNav} aria-label="Mobile Bottom Navigation">
      {tabs.map((tab) => {
        const isActive = pathname === tab.href || (tab.href !== "/dashboard" && tab.href !== "/lawyer/dashboard" && pathname.startsWith(tab.href));
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
