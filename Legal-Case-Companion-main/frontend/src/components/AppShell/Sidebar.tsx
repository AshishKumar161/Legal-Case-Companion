"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
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
  const { user } = useAuth();

  // Active matter context detection
  const isInsideCase = pathname.startsWith("/cases/") && pathname !== "/cases/new";
  const caseIdMatch = pathname.match(/^\/cases\/([^/]+)/);
  const activeCaseId = caseIdMatch ? caseIdMatch[1] : null;

  const role = user?.role || "CLIENT";

  // Navigation Items per Role
  const clientNav = [
    { label: "Overview", href: "/dashboard", icon: "📊" },
    { label: "My Matters", href: "/dashboard", icon: "⚖" },
    { label: "Find Lawyers", href: "/lawyers", icon: "🔍" },
  ];

  const lawyerNav = [
    { label: "Practice Overview", href: "/lawyer/dashboard", icon: "📈" },
    { label: "Profile & Slots", href: "/lawyer/profile", icon: "📅" },
    { label: "Lawyer Directory", href: "/lawyers", icon: "👥" },
    { label: "Client View", href: "/dashboard", icon: "📁" },
  ];

  const adminNav = [
    { label: "Console Overview", href: "/admin/dashboard", icon: "🛡" },
    { label: "Lawyer Directory", href: "/lawyers", icon: "⚖" },
    { label: "Client Workspace", href: "/dashboard", icon: "📁" },
  ];

  const navItems =
    role === "LAWYER" ? lawyerNav : role === "ADMIN" ? adminNav : clientNav;

  return (
    <>
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.7)",
            zIndex: 99,
          }}
        />
      )}

      <aside
        className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ""} ${
          mobileOpen ? styles.sidebarMobileOpen : ""
        }`}
      >
        {/* Brand Header */}
        <div className={styles.sidebarHeader}>
          <Link href={role === "LAWYER" ? "/lawyer/dashboard" : "/dashboard"} className={styles.brandLink}>
            <div className={styles.brandIcon}>⚖</div>
            {!collapsed && <span className={styles.brandText}>Legal Case Companion</span>}
          </Link>

          <button
            onClick={onToggleCollapse}
            className={styles.collapseToggleBtn}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label="Toggle sidebar"
          >
            {collapsed ? "→" : "←"}
          </button>
        </div>

        {/* Matter Context Ribbon (if inside /cases/[id]) */}
        {isInsideCase && activeCaseId && !collapsed && (
          <div className={styles.matterContextCard}>
            <div className={styles.matterContextLabel}>Active Matter</div>
            <div className={styles.matterContextTitle}>REF: #{activeCaseId.slice(0, 8).toUpperCase()}</div>
            <Link
              href={`/cases/${activeCaseId}`}
              style={{
                fontSize: "11px",
                color: "var(--accent-secondary)",
                marginTop: "4px",
                display: "inline-block",
                fontWeight: 600,
              }}
            >
              Workspace View →
            </Link>
          </div>
        )}

        {/* Main Navigation */}
        <div className={styles.navSection}>
          <div className={styles.navGroup}>
            {!collapsed && <div className={styles.navGroupLabel}>Core Navigation</div>}
            {navItems.map((item, idx) => {
              const isActive =
                item.href === "/dashboard"
                  ? pathname === "/dashboard"
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

          {/* Dedicated Matter Quick Actions */}
          {!collapsed && role === "CLIENT" && (
            <div className={styles.navGroup} style={{ marginTop: "12px" }}>
              <div className={styles.navGroupLabel}>Quick Actions</div>
              <Link
                href="/cases/new"
                className={styles.navItem}
                style={{ color: "var(--accent-secondary)" }}
                onClick={onCloseMobile}
              >
                <span className={styles.navIcon}>+</span>
                <span>Open New Matter</span>
              </Link>
            </div>
          )}
        </div>

        {/* User Footer Summary */}
        <div className={styles.sidebarFooter}>
          <div className={styles.userSummary}>
            <div className={styles.userAvatar}>
              {user?.full_name?.charAt(0) || user?.email?.charAt(0).toUpperCase() || "U"}
            </div>
            {!collapsed && (
              <div className={styles.userInfo}>
                <div className={styles.userName}>{user?.full_name || user?.email?.split("@")[0]}</div>
                <div className={styles.userRole}>{user?.role || "CLIENT"}</div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
