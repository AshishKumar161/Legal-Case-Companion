"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { apiClient } from "@/api/client";
import { NotificationItem } from "@/types";
import Link from "next/link";

type FilterTab = "ALL" | "ACTION_REQUIRED" | "HEARINGS_DEADLINES" | "DOCUMENTS";

export function NotificationBell() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [activeFilter, setActiveFilter] = useState<FilterTab>("ALL");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await apiClient.get("/api/v1/notifications?limit=25");
      const items = res?.items || (Array.isArray(res) ? res : []);
      setNotifications(items);

      const unreadRes = await apiClient.get("/api/v1/notifications/unread-count");
      setUnreadCount(unreadRes?.unread_count ?? items.filter((n: NotificationItem) => !n.is_read).length);
    } catch {
      // Silently catch in polling / unauthenticated state
    }
  }, []);

  useEffect(() => {
    void fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000); // 15s refresh
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const markAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.post(`/api/v1/notifications/${id}/read`, {});
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error("Failed to mark notification as read", err);
    }
  };

  const markAllRead = async () => {
    try {
      await apiClient.post("/api/v1/notifications/read-all", {});
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error("Failed to mark all notifications as read", err);
    }
  };

  const getCategory = (type: string): "ACTION_REQUIRED" | "HEARINGS_DEADLINES" | "DOCUMENTS" | "GENERAL" => {
    if (type.includes("TASK") || type.includes("ACTION") || type.includes("CONSULTATION_REQUESTED")) {
      return "ACTION_REQUIRED";
    }
    if (type.includes("DEADLINE") || type.includes("HEARING") || type.includes("LIMITATION")) {
      return "HEARINGS_DEADLINES";
    }
    if (type.includes("DOCUMENT") || type.includes("EVIDENCE") || type.includes("SECURITY")) {
      return "DOCUMENTS";
    }
    return "GENERAL";
  };

  const getTypeBadge = (type: string) => {
    if (type.includes("DEADLINE") || type.includes("OVERDUE") || type.includes("LIMITATION")) {
      return { bg: "rgba(239, 68, 68, 0.15)", color: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.3)", label: "Limitation / Deadline" };
    }
    if (type.includes("HEARING")) {
      return { bg: "rgba(245, 158, 11, 0.15)", color: "#f59e0b", border: "1px solid rgba(245, 158, 11, 0.3)", label: "Court Listing" };
    }
    if (type.includes("DOCUMENT")) {
      return { bg: "rgba(59, 130, 246, 0.15)", color: "#60a5fa", border: "1px solid rgba(59, 130, 246, 0.3)", label: "Evidence Vault" };
    }
    if (type.includes("AI")) {
      return { bg: "rgba(109, 124, 255, 0.15)", color: "#8d98ff", border: "1px solid rgba(109, 124, 255, 0.3)", label: "Case Copilot" };
    }
    if (type.includes("CONSULTATION")) {
      return { bg: "rgba(16, 185, 129, 0.15)", color: "#10b981", border: "1px solid rgba(16, 185, 129, 0.3)", label: "Consultation" };
    }
    return { bg: "rgba(148, 163, 184, 0.12)", color: "#94a3b8", border: "1px solid rgba(148, 163, 184, 0.2)", label: "Notice" };
  };

  const filteredNotifications = notifications.filter((n) => {
    if (activeFilter === "ALL") return true;
    return getCategory(n.type) === activeFilter;
  });

  // Calculate deep link target based on item metadata
  const getNotificationLink = (n: NotificationItem) => {
    if (n.case_id) {
      if (n.type.includes("HEARING") || n.type.includes("DEADLINE") || n.type.includes("TASK")) {
        return `/cases/${n.case_id}?tab=workflow`;
      }
      if (n.type.includes("DOCUMENT")) {
        return `/cases/${n.case_id}?tab=documents`;
      }
      if (n.type.includes("AI")) {
        return `/cases/${n.case_id}?tab=copilot`;
      }
      return `/cases/${n.case_id}`;
    }
    if (n.type.includes("CONSULTATION")) {
      return "/dashboard";
    }
    return null;
  };

  return (
    <div style={{ position: "relative" }} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Workflow Notifications"
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "36px",
          height: "36px",
          borderRadius: "var(--radius-sm)",
          background: isOpen ? "var(--surface-hover)" : "var(--surface-subtle)",
          border: "1px solid var(--border-subtle)",
          color: "var(--text-primary)",
          fontSize: "16px",
          transition: "all 0.15s ease",
          cursor: "pointer",
        }}
      >
        🔔
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              background: "var(--error)",
              color: "#fff",
              fontSize: "10px",
              fontWeight: 700,
              padding: "1px 5px",
              borderRadius: "8px",
              boxShadow: "0 0 8px rgba(239, 68, 68, 0.6)",
            }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            right: 0,
            top: "46px",
            width: "390px",
            maxHeight: "520px",
            overflowY: "auto",
            zIndex: 1000,
            padding: "16px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-hover)",
            boxShadow: "var(--shadow-lg)",
            background: "var(--surface-elevated)",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid var(--border-subtle)",
              paddingBottom: "10px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>
                Matter Notifications
              </span>
              {unreadCount > 0 && (
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "10px",
                    background: "rgba(239, 68, 68, 0.15)",
                    color: "#ef4444",
                  }}
                >
                  {unreadCount} UNREAD
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                style={{
                  fontSize: "11px",
                  color: "var(--accent-secondary)",
                  fontWeight: 600,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Workflow Filter Tabs */}
          <div style={{ display: "flex", gap: "4px", overflowX: "auto", paddingBottom: "4px" }}>
            <button
              onClick={() => setActiveFilter("ALL")}
              style={{
                fontSize: "11px",
                fontWeight: 600,
                padding: "4px 8px",
                borderRadius: "4px",
                background: activeFilter === "ALL" ? "var(--surface-card)" : "transparent",
                color: activeFilter === "ALL" ? "var(--text-primary)" : "var(--text-muted)",
                border: activeFilter === "ALL" ? "1px solid var(--border-subtle)" : "1px solid transparent",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              All
            </button>
            <button
              onClick={() => setActiveFilter("ACTION_REQUIRED")}
              style={{
                fontSize: "11px",
                fontWeight: 600,
                padding: "4px 8px",
                borderRadius: "4px",
                background: activeFilter === "ACTION_REQUIRED" ? "var(--surface-card)" : "transparent",
                color: activeFilter === "ACTION_REQUIRED" ? "var(--text-primary)" : "var(--text-muted)",
                border: activeFilter === "ACTION_REQUIRED" ? "1px solid var(--border-subtle)" : "1px solid transparent",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              Action Required
            </button>
            <button
              onClick={() => setActiveFilter("HEARINGS_DEADLINES")}
              style={{
                fontSize: "11px",
                fontWeight: 600,
                padding: "4px 8px",
                borderRadius: "4px",
                background: activeFilter === "HEARINGS_DEADLINES" ? "var(--surface-card)" : "transparent",
                color: activeFilter === "HEARINGS_DEADLINES" ? "var(--text-primary)" : "var(--text-muted)",
                border: activeFilter === "HEARINGS_DEADLINES" ? "1px solid var(--border-subtle)" : "1px solid transparent",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              Hearings & Deadlines
            </button>
            <button
              onClick={() => setActiveFilter("DOCUMENTS")}
              style={{
                fontSize: "11px",
                fontWeight: 600,
                padding: "4px 8px",
                borderRadius: "4px",
                background: activeFilter === "DOCUMENTS" ? "var(--surface-card)" : "transparent",
                color: activeFilter === "DOCUMENTS" ? "var(--text-primary)" : "var(--text-muted)",
                border: activeFilter === "DOCUMENTS" ? "1px solid var(--border-subtle)" : "1px solid transparent",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              Evidence
            </button>
          </div>

          {/* List Content */}
          {filteredNotifications.length === 0 ? (
            <div style={{ padding: "28px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "12px" }}>
              No notifications in this category.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {filteredNotifications.map((n) => {
                const badge = getTypeBadge(n.type);
                const targetLink = getNotificationLink(n);

                return (
                  <div
                    key={n.id}
                    style={{
                      padding: "12px",
                      borderRadius: "var(--radius-sm)",
                      background: n.is_read ? "var(--surface-card)" : "rgba(79, 91, 247, 0.08)",
                      border: n.is_read ? "1px solid var(--border-subtle)" : "1px solid rgba(79, 91, 247, 0.3)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: badge.bg,
                          color: badge.color,
                          border: badge.border,
                        }}
                      >
                        {badge.label}
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                          {new Date(n.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        {!n.is_read && (
                          <button
                            onClick={(e) => markAsRead(n.id, e)}
                            title="Mark as read"
                            style={{
                              fontSize: "11px",
                              color: "var(--text-muted)",
                              background: "transparent",
                              border: "none",
                              cursor: "pointer",
                            }}
                          >
                            ✓
                          </button>
                        )}
                      </div>
                    </div>

                    <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                      {n.title}
                    </div>

                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.45 }}>
                      {n.message}
                    </div>

                    {targetLink && (
                      <Link
                        href={targetLink}
                        onClick={() => setIsOpen(false)}
                        style={{
                          fontSize: "11px",
                          color: "var(--accent-secondary)",
                          marginTop: "4px",
                          fontWeight: 600,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        Navigate to Object →
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div
            style={{
              padding: "10px 14px",
              borderTop: "1px solid var(--border-subtle)",
              textAlign: "center",
              background: "rgba(0, 0, 0, 0.2)",
            }}
          >
            <Link
              href="/notifications"
              onClick={() => setIsOpen(false)}
              style={{
                fontSize: "12px",
                color: "var(--accent-secondary, #8d98ff)",
                fontWeight: 600,
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              Open Full Notifications Center →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
