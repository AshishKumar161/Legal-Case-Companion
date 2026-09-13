"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import {
  HomeIcon,
  CaseIcon,
  CalendarIcon,
  DocumentIcon,
  LawyerIcon,
  ChatIcon,
  BellIcon,
  SettingsIcon,
  CourthouseIcon,
  ShieldIcon,
  PlusIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  AssistantIcon,
} from "@/components/ui/Icons";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  // Active case context detection
  const isInsideCase = pathname.startsWith("/cases/") && pathname !== "/cases/new";
  const caseIdMatch = pathname.match(/^\/cases\/([^/]+)/);
  const activeCaseId = caseIdMatch ? caseIdMatch[1] : null;

  const role = user?.role;

  // Canonical Simple Client Navigation (Section 4)
  const clientPrimaryNav = [
    { label: "Home", href: "/dashboard", icon: <HomeIcon size={18} /> },
    { label: "My Case", href: "/cases", icon: <CaseIcon size={18} /> },
    { label: "Hearings", href: "/calendar", icon: <CalendarIcon size={18} /> },
    { label: "Documents", href: "/documents", icon: <DocumentIcon size={18} /> },
    { label: "My Lawyer", href: "/lawyers", icon: <LawyerIcon size={18} /> },
    { label: "Messages", href: "/messages", icon: <ChatIcon size={18} /> },
    { label: "AI Advisor", href: "/ai-advisor", icon: <AssistantIcon size={18} /> },
  ];

  const clientSecondaryNav = [
    { label: "Notifications", href: "/notifications", icon: <BellIcon size={18} /> },
    { label: "Settings", href: "/settings", icon: <SettingsIcon size={18} /> },
  ];

  const lawyerPrimaryNav = [
    { label: "Practice Hub", href: "/lawyer/dashboard", icon: <HomeIcon size={18} /> },
    { label: "Cases", href: "/cases", icon: <CaseIcon size={18} /> },
    { label: "Hearings", href: "/calendar", icon: <CalendarIcon size={18} /> },
    { label: "Court Tracking", href: "/court-tracking", icon: <CourthouseIcon size={18} /> },
    { label: "Clients", href: "/clients", icon: <LawyerIcon size={18} /> },
    { label: "Documents", href: "/documents", icon: <DocumentIcon size={18} /> },
    { label: "Consultations", href: "/consultations", icon: <ChatIcon size={18} /> },
    { label: "AI Advisor", href: "/ai-advisor", icon: <AssistantIcon size={18} /> },
  ];

  const lawyerSecondaryNav = [
    { label: "Trust Center", href: "/trust", icon: <ShieldIcon size={18} /> },
    { label: "Settings", href: "/settings", icon: <SettingsIcon size={18} /> },
  ];

  const adminPrimaryNav = [
    { label: "Dashboard", href: "/admin/dashboard", icon: <HomeIcon size={18} /> },
    { label: "Cases", href: "/cases", icon: <CaseIcon size={18} /> },
    { label: "Verifications", href: "/admin/verification", icon: <ShieldIcon size={18} /> },
    { label: "Users & Team", href: "/admin/users", icon: <LawyerIcon size={18} /> },
    { label: "Hearings", href: "/calendar", icon: <CalendarIcon size={18} /> },
    { label: "Documents", href: "/documents", icon: <DocumentIcon size={18} /> },
  ];

  const adminSecondaryNav = [
    { label: "Reports", href: "/admin/reports", icon: <DocumentIcon size={18} /> },
    { label: "Settings", href: "/settings", icon: <SettingsIcon size={18} /> },
  ];

  const primaryItems =
    loading && !role
      ? []
      : role === "LAWYER"
      ? lawyerPrimaryNav
      : role === "ADMIN"
      ? adminPrimaryNav
      : clientPrimaryNav;

  const secondaryItems =
    loading && !role
      ? []
      : role === "LAWYER"
      ? lawyerSecondaryNav
      : role === "ADMIN"
      ? adminSecondaryNav
      : clientSecondaryNav;

  return (
    <>
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.4)",
            backdropFilter: "blur(2px)",
            zIndex: 99,
          }}
          aria-hidden="true"
        />
      )}

      <aside
        className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ""} ${
          mobileOpen ? styles.sidebarMobileOpen : ""
        }`}
        aria-label="Sidebar Navigation"
      >
        {/* Brand Header */}
        <div className={styles.sidebarHeader}>
          <Link
            href={role === "LAWYER" ? "/lawyer/dashboard" : "/dashboard"}
            className={styles.brandLink}
          >
            <div className={styles.brandIcon} style={{ background: "#0f172a", border: "1px solid rgba(255, 255, 255, 0.15)", overflow: "hidden", padding: "3px" }}>
              <Image
                src="/logo-icon-white.png"
                alt="LCC Logo"
                width={28}
                height={28}
                style={{ objectFit: "contain", width: "auto", height: "auto" }}
                priority
              />
            </div>
            {!collapsed && (
              <div className={styles.brandText}>
                <span className={styles.brandTitle}>LCC</span>
                <span className={styles.brandTagline}>Legal Case Companion</span>
              </div>
            )}
          </Link>

          <button
            onClick={onToggleCollapse}
            className={styles.collapseToggleBtn}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ArrowRightIcon size={16} /> : <ArrowLeftIcon size={16} />}
          </button>
        </div>

        {/* Case Context Ribbon (if inside /cases/[id]) */}
        {isInsideCase && activeCaseId && !collapsed && (
          <div className={styles.matterContextCard}>
            <div className={styles.matterContextLabel}>Active Case</div>
            <div className={styles.matterContextTitle}>Case #{activeCaseId.slice(0, 8).toUpperCase()}</div>
            <Link
              href={`/cases/${activeCaseId}`}
              style={{
                fontSize: "12px",
                color: "var(--navy-secondary)",
                marginTop: "4px",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontWeight: 600,
              }}
            >
              <span>View Case</span>
              <ArrowRightIcon size={12} />
            </Link>
          </div>
        )}

        {/* Navigation Sections */}
        <div className={styles.navSection}>
          <div className={styles.navGroup}>
            {primaryItems.map((item, idx) => {
              const isActive =
                item.href === "/dashboard" || item.href === "/lawyer/dashboard" || item.href === "/admin/dashboard"
                  ? pathname === item.href
                  : pathname.startsWith(item.href);

              return (
                <Link
                  key={idx}
                  href={item.href}
                  className={`${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
                  onClick={onCloseMobile}
                  title={collapsed ? item.label : undefined}
                >
                  <span className={styles.navIcon}>{item.icon}</span>
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>

          <div className={styles.navGroupDivider} />

          <div className={styles.navGroup}>
            {secondaryItems.map((item, idx) => {
              const isActive = pathname === item.href || (item.href !== "/settings" && pathname.startsWith(item.href));
              return (
                <Link
                  key={idx}
                  href={item.href}
                  className={`${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
                  onClick={onCloseMobile}
                  title={collapsed ? item.label : undefined}
                >
                  <span className={styles.navIcon}>{item.icon}</span>
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>

          {/* Quick Action for Clients */}
          {!collapsed && role !== "LAWYER" && role !== "ADMIN" && (
            <div style={{ marginTop: "auto", paddingTop: "8px" }}>
              <Link
                href="/cases/new"
                className="btn btn-secondary"
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: "13px",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                }}
                onClick={onCloseMobile}
              >
                <PlusIcon size={16} />
                <span>Start a Case</span>
              </Link>
            </div>
          )}
        </div>

        {/* User Footer Summary */}
        <div className={styles.sidebarFooter}>
          <Link
            href="/settings"
            className={styles.userSummary}
            style={{ textDecoration: "none", color: "inherit", width: "100%" }}
          >
            <div className={styles.userAvatar}>
              {user?.full_name?.charAt(0) || user?.email?.charAt(0).toUpperCase() || "U"}
            </div>
            {!collapsed && (
              <div className={styles.userInfo}>
                <div className={styles.userName}>{user?.full_name || user?.email?.split("@")[0]}</div>
                <div className={styles.userRole}>
                  {role === "LAWYER" ? "Advocate" : role === "ADMIN" ? "Administrator" : "Client"}
                </div>
              </div>
            )}
          </Link>
        </div>
      </aside>
    </>
  );
}
