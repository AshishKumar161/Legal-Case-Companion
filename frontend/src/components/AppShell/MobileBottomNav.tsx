"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import {
  HomeIcon,
  CaseIcon,
  CalendarIcon,
  DocumentIcon,
  CourthouseIcon,
  AssistantIcon,
} from "@/components/ui/Icons";
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
        { label: "Practice", href: "/lawyer/dashboard", icon: <HomeIcon size={18} /> },
        { label: "Cases", href: "/cases", icon: <CaseIcon size={18} /> },
        { label: "Court", href: "/court-tracking", icon: <CourthouseIcon size={18} /> },
        { label: "Calendar", href: "/calendar", icon: <CalendarIcon size={18} /> },
        { label: "AI", href: "/ai-advisor", icon: <AssistantIcon size={18} /> },
      ]
    : [
        { label: "Home", href: "/dashboard", icon: <HomeIcon size={18} /> },
        { label: "My Case", href: "/cases", icon: <CaseIcon size={18} /> },
        { label: "Hearings", href: "/calendar", icon: <CalendarIcon size={18} /> },
        { label: "Documents", href: "/documents", icon: <DocumentIcon size={18} /> },
        { label: "AI", href: "/ai-advisor", icon: <AssistantIcon size={18} /> },
      ];

  return (
    <nav className={styles.mobileBottomNav} aria-label="Mobile Navigation">
      {tabs.map((tab) => {
        const isActive =
          pathname === tab.href ||
          (tab.href !== "/dashboard" && tab.href !== "/lawyer/dashboard" && pathname.startsWith(tab.href));

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
