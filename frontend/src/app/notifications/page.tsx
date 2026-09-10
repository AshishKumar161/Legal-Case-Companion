"use client";

import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import { NotificationItem } from "@/types";
import Link from "next/link";
import styles from "./notifications.module.css";

type TabType = "ALL" | "UNREAD" | "CASE" | "TASK" | "CONSULTATION" | "PAYMENT" | "SECURITY";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<TabType>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(20);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isMutating, setIsMutating] = useState<boolean>(false);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await apiClient.get("/api/v1/notifications/unread-count");
      setUnreadCount(res?.unread_count ?? 0);
    } catch {
      // Ignore in background
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const skip = (page - 1) * limit;
      let url = `/api/v1/notifications?skip=${skip}&limit=${limit}`;

      if (activeTab === "UNREAD") {
        url += "&is_read=false";
      } else if (activeTab !== "ALL") {
        url += `&category=${activeTab}`;
      }

      if (searchQuery.trim()) {
        url += `&search=${encodeURIComponent(searchQuery.trim())}`;
      }

      const res = await apiClient.get(url);
      const items = res?.items || (Array.isArray(res) ? res : []);
      setNotifications(items);
      setTotalCount(res?.total ?? items.length);
      setSelectedIds([]);
      void fetchUnreadCount();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load notifications";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [activeTab, page, limit, searchQuery, fetchUnreadCount]);

  useEffect(() => {
    void fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkAsRead = async (id: string) => {
    try {
      await apiClient.post(`/api/v1/notifications/${id}/read`, {});
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error("Failed to mark as read", err);
    }
  };

  const handleMarkAsUnread = async (id: string) => {
    try {
      await apiClient.post(`/api/v1/notifications/${id}/unread`, {});
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: false } : n))
      );
      setUnreadCount((prev) => prev + 1);
    } catch (err) {
      console.error("Failed to mark as unread", err);
    }
  };

  const handleMarkAllRead = async () => {
    setIsMutating(true);
    try {
      await apiClient.post("/api/v1/notifications/read-all", {});
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error("Failed to mark all as read", err);
    } finally {
      setIsMutating(false);
    }
  };

  const handleBulkRead = async () => {
    if (selectedIds.length === 0) return;
    setIsMutating(true);
    try {
      await apiClient.post("/api/v1/notifications/bulk-read", {
        notification_ids: selectedIds,
      });
      setNotifications((prev) =>
        prev.map((n) => (selectedIds.includes(n.id) ? { ...n, is_read: true } : n))
      );
      setSelectedIds([]);
      void fetchUnreadCount();
    } catch (err) {
      console.error("Failed to bulk mark read", err);
    } finally {
      setIsMutating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api/v1/notifications/${id}`);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      setSelectedIds((prev) => prev.filter((item) => item !== id));
      void fetchUnreadCount();
    } catch (err) {
      console.error("Failed to delete notification", err);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    setIsMutating(true);
    try {
      await apiClient.post("/api/v1/notifications/bulk-delete", {
        notification_ids: selectedIds,
      });
      setNotifications((prev) => prev.filter((n) => !selectedIds.includes(n.id)));
      setSelectedIds([]);
      void fetchUnreadCount();
    } catch (err) {
      console.error("Failed to bulk delete notifications", err);
    } finally {
      setIsMutating(false);
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAllVisible = () => {
    if (selectedIds.length === notifications.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(notifications.map((n) => n.id));
    }
  };

  const getBadgeStyle = (type: string) => {
    if (type.includes("DEADLINE") || type.includes("OVERDUE") || type.includes("LIMITATION")) {
      return {
        bg: "rgba(239, 68, 68, 0.15)",
        color: "#ef4444",
        border: "1px solid rgba(239, 68, 68, 0.3)",
        label: "Limitation / Deadline",
      };
    }
    if (type.includes("HEARING")) {
      return {
        bg: "rgba(245, 158, 11, 0.15)",
        color: "#f59e0b",
        border: "1px solid rgba(245, 158, 11, 0.3)",
        label: "Court Listing",
      };
    }
    if (type.includes("DOCUMENT") || type.includes("EVIDENCE")) {
      return {
        bg: "rgba(59, 130, 246, 0.15)",
        color: "#60a5fa",
        border: "1px solid rgba(59, 130, 246, 0.3)",
        label: "Evidence Vault",
      };
    }
    if (type.includes("CONSULTATION")) {
      return {
        bg: "rgba(16, 185, 129, 0.15)",
        color: "#10b981",
        border: "1px solid rgba(16, 185, 129, 0.3)",
        label: "Consultation",
      };
    }
    if (type.includes("PAYMENT")) {
      return {
        bg: "rgba(168, 85, 247, 0.15)",
        color: "#c084fc",
        border: "1px solid rgba(168, 85, 247, 0.3)",
        label: "Payment",
      };
    }
    if (type.includes("TASK")) {
      return {
        bg: "rgba(234, 179, 8, 0.15)",
        color: "#facc15",
        border: "1px solid rgba(234, 179, 8, 0.3)",
        label: "Task Update",
      };
    }
    return {
      bg: "rgba(148, 163, 184, 0.12)",
      color: "#94a3b8",
      border: "1px solid rgba(148, 163, 184, 0.2)",
      label: "Case Notice",
    };
  };

  const getResourceLink = (n: NotificationItem) => {
    if (n.case_id) {
      if (n.type.includes("HEARING") || n.type.includes("DEADLINE") || n.type.includes("TASK")) {
        return `/cases/${n.case_id}?tab=workflow`;
      }
      if (n.type.includes("DOCUMENT")) {
        return `/cases/${n.case_id}?tab=documents`;
      }
      return `/cases/${n.case_id}`;
    }
    if (n.consultation_id || n.type.includes("CONSULTATION")) {
      return "/dashboard";
    }
    return null;
  };

  const formatTime = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const totalPages = Math.ceil(totalCount / limit) || 1;

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerText}>
          <div className={styles.categoryTag}>
            <span>⚡ Real-Time Center</span>
          </div>
          <h1 className={styles.pageTitle}>
            Notifications Center
            {unreadCount > 0 && <span className={styles.unreadPill}>{unreadCount} unread</span>}
          </h1>
          <p className={styles.subtitle}>
            Review case timeline updates, court listings, task assignments, and payment alerts.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            onClick={handleMarkAllRead}
            disabled={unreadCount === 0 || isMutating}
            className={`${styles.actionButton} ${styles.actionButtonPrimary}`}
            aria-label="Mark all notifications as read"
          >
            ✓ Mark All as Read
          </button>
          <button
            onClick={() => void fetchNotifications()}
            disabled={loading}
            className={styles.actionButton}
            aria-label="Refresh notification feed"
          >
            🔄 Refresh
          </button>
        </div>
      </header>

      {/* Filter Controls Bar */}
      <section className={styles.controlsBar} aria-label="Notification filters">
        <div className={styles.tabsRow} role="tablist">
          {[
            { id: "ALL", label: "All" },
            { id: "UNREAD", label: `Unread (${unreadCount})` },
            { id: "CASE", label: "Case Updates" },
            { id: "TASK", label: "Tasks & Deadlines" },
            { id: "CONSULTATION", label: "Consultations" },
            { id: "PAYMENT", label: "Payments" },
            { id: "SECURITY", label: "Security & Notices" },
          ].map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => {
                setActiveTab(tab.id as TabType);
                setPage(1);
              }}
              className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className={styles.searchAndOptions}>
          <div className={styles.searchInputWrapper}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="search"
              placeholder="Search notifications by keyword..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className={styles.searchInput}
              aria-label="Search notifications"
            />
          </div>
        </div>
      </section>

      {/* Bulk Action Toolbar */}
      {selectedIds.length > 0 && (
        <aside className={styles.bulkToolbar} aria-label="Bulk actions toolbar">
          <div className={styles.bulkInfo}>
            <span>{selectedIds.length} notifications selected</span>
          </div>
          <div className={styles.bulkActions}>
            <button
              onClick={handleBulkRead}
              disabled={isMutating}
              className={styles.bulkBtn}
              aria-label="Mark selected notifications as read"
            >
              ✓ Mark Read
            </button>
            <button
              onClick={handleBulkDelete}
              disabled={isMutating}
              className={`${styles.bulkBtn} ${styles.bulkBtnDanger}`}
              aria-label="Delete selected notifications"
            >
              🗑️ Delete
            </button>
            <button
              onClick={() => setSelectedIds([])}
              className={styles.bulkBtn}
              aria-label="Deselect all notifications"
            >
              Cancel
            </button>
          </div>
        </aside>
      )}

      {/* Error state */}
      {error && (
        <div className={styles.emptyCard} style={{ borderColor: "rgba(239, 68, 68, 0.4)" }}>
          <div className={styles.emptyIcon}>⚠️</div>
          <h2 className={styles.emptyTitle}>Unable to load notifications</h2>
          <p className={styles.emptySubtitle}>{error}</p>
          <button
            onClick={() => void fetchNotifications()}
            className={styles.actionButton}
            style={{ marginTop: "16px" }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && !error && (
        <div className={styles.emptyCard}>
          <div className={styles.emptyIcon}>⏳</div>
          <h2 className={styles.emptyTitle}>Loading notifications...</h2>
          <p className={styles.emptySubtitle}>Synchronizing your case notices and listings.</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && notifications.length === 0 && (
        <div className={styles.emptyCard}>
          <div className={styles.emptyIcon}>🎉</div>
          <h2 className={styles.emptyTitle}>
            {activeTab === "UNREAD" ? "You're all caught up!" : "No notifications found"}
          </h2>
          <p className={styles.emptySubtitle}>
            {activeTab === "UNREAD"
              ? "There are no pending unread notifications for your account."
              : "No notification records match the selected filter or search query."}
          </p>
        </div>
      )}

      {/* Feed List */}
      {!loading && !error && notifications.length > 0 && (
        <div className={styles.feedList} role="feed" aria-busy={isMutating}>
          <div style={{ padding: "4px 8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <input
              type="checkbox"
              id="select-all-visible"
              checked={selectedIds.length === notifications.length && notifications.length > 0}
              onChange={handleSelectAllVisible}
              className={styles.customCheckbox}
              aria-label="Select all visible notifications"
            />
            <label
              htmlFor="select-all-visible"
              style={{ fontSize: "12px", color: "var(--text-muted)", cursor: "pointer" }}
            >
              Select all visible ({notifications.length})
            </label>
          </div>

          {notifications.map((n) => {
            const badge = getBadgeStyle(n.type);
            const targetLink = getResourceLink(n);
            const isSelected = selectedIds.includes(n.id);

            return (
              <article
                key={n.id}
                className={`${styles.card} ${!n.is_read ? styles.cardUnread : ""}`}
                aria-label={`${n.is_read ? "Read" : "Unread"} notification: ${n.title}`}
              >
                <div className={styles.checkboxWrapper}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => handleToggleSelect(n.id)}
                    className={styles.customCheckbox}
                    aria-label={`Select notification ${n.title}`}
                  />
                </div>

                <div className={styles.cardBody}>
                  <div className={styles.cardMeta}>
                    <span
                      className={styles.badge}
                      style={{
                        backgroundColor: badge.bg,
                        color: badge.color,
                        border: badge.border,
                      }}
                    >
                      {badge.label}
                    </span>
                    <time dateTime={n.created_at} className={styles.timestamp}>
                      {formatTime(n.created_at)}
                    </time>
                  </div>

                  <h3 className={`${styles.cardTitle} ${!n.is_read ? styles.cardTitleUnread : ""}`}>
                    {n.title}
                  </h3>

                  <p className={styles.cardMessage}>{n.message}</p>

                  <div className={styles.cardFooter}>
                    {targetLink ? (
                      <Link
                        href={targetLink}
                        onClick={() => {
                          if (!n.is_read) {
                            void handleMarkAsRead(n.id);
                          }
                        }}
                        className={styles.deepLink}
                      >
                        View Related Resource →
                      </Link>
                    ) : (
                      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                        Notice only
                      </span>
                    )}

                    <div className={styles.itemActions}>
                      {n.is_read ? (
                        <button
                          onClick={() => handleMarkAsUnread(n.id)}
                          className={styles.iconBtn}
                          title="Mark as unread"
                          aria-label="Mark as unread"
                        >
                          ✉️ Unread
                        </button>
                      ) : (
                        <button
                          onClick={() => handleMarkAsRead(n.id)}
                          className={styles.iconBtn}
                          title="Mark as read"
                          aria-label="Mark as read"
                        >
                          ✓ Read
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(n.id)}
                        className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                        title="Delete notification"
                        aria-label="Delete notification"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Pagination Controls */}
      {!loading && !error && totalCount > limit && (
        <footer className={styles.paginationBar} aria-label="Pagination Navigation">
          <span className={styles.paginationText}>
            Page {page} of {totalPages} ({totalCount} total notifications)
          </span>
          <div className={styles.paginationButtons}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className={styles.actionButton}
              aria-label="Previous page"
            >
              ← Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className={styles.actionButton}
              aria-label="Next page"
            >
              Next →
            </button>
          </div>
        </footer>
      )}
    </div>
  );
}
