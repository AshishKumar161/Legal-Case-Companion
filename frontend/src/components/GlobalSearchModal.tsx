"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import { CaseItem, LawyerProfileItem, CourtCaseSummary } from "@/types";
import styles from "./GlobalSearchModal.module.css";

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SearchResultAction {
  id: string;
  category: "Recent" | "Case" | "Hearing" | "Document" | "Lawyer" | "Destination" | "Court Record";
  title: string;
  subtitle: string;
  tag: string;
  tagColor: { bg: string; text: string };
  action: () => void;
}

export function GlobalSearchModal({ isOpen, onClose }: GlobalSearchModalProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [matchingCases, setMatchingCases] = useState<CaseItem[]>([]);
  const [matchingLawyers, setMatchingLawyers] = useState<LawyerProfileItem[]>([]);
  const [matchingCourtCases, setMatchingCourtCases] = useState<CourtCaseSummary[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Load recent searches on modal open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      try {
        const saved = localStorage.getItem("lcc_recent_searches");
        if (saved) {
          setRecentSearches(JSON.parse(saved).slice(0, 4));
        }
      } catch {
        // LocalStorage blocked or unavailable
      }
    } else {
      setQuery("");
      setMatchingCases([]);
      setMatchingLawyers([]);
      setMatchingCourtCases([]);
      setSelectedIndex(0);
    }
  }, [isOpen]);

  const saveRecentSearch = useCallback((term: string) => {
    try {
      const existing = recentSearches.filter((s) => s.toLowerCase() !== term.toLowerCase());
      const updated = [term, ...existing].slice(0, 5);
      setRecentSearches(updated);
      localStorage.setItem("lcc_recent_searches", JSON.stringify(updated));
    } catch {
      // Ignored if storage unavailable
    }
  }, [recentSearches]);

  // Perform bounded search across authorized cases, lawyers, and court cases
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setMatchingCases([]);
      setMatchingLawyers([]);
      setMatchingCourtCases([]);
      setSelectedIndex(0);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const [casesRes, lawyersRes, courtRes] = await Promise.all([
          apiClient.get(`/api/v1/cases?search=${encodeURIComponent(query.trim())}&limit=5`).catch(() => ({ items: [] })),
          apiClient.get(`/api/v1/lawyers?search=${encodeURIComponent(query.trim())}&limit=4`).catch(() => ({ items: [] })),
          apiClient.get(`/api/v1/court-cases?search=${encodeURIComponent(query.trim())}&limit=3`).catch(() => ({ items: [] })),
        ]);

        setMatchingCases(casesRes?.items || (Array.isArray(casesRes) ? casesRes : []));
        setMatchingLawyers(lawyersRes?.items || (Array.isArray(lawyersRes) ? lawyersRes : []));
        setMatchingCourtCases(courtRes?.items || (Array.isArray(courtRes) ? courtRes : []));
        setSelectedIndex(0);
      } catch (err) {
        console.error("Global search error:", err);
      } finally {
        setSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  // Build unified flattened result actions list for arrow navigation
  const resultActions = useMemo<SearchResultAction[]>(() => {
    const actions: SearchResultAction[] = [];

    if (query.length < 2) {
      // Recent searches first
      recentSearches.forEach((rec) => {
        actions.push({
          id: `recent-${rec}`,
          category: "Recent",
          title: rec,
          subtitle: "Recent search term",
          tag: "Recent",
          tagColor: { bg: "rgba(148, 163, 184, 0.15)", text: "#94a3b8" },
          action: () => setQuery(rec),
        });
      });

      // Quick destinations
      actions.push(
        {
          id: "dest-court-tracking",
          category: "Destination",
          title: "🏛 Court Case Tracking",
          subtitle: "Search official eCourts CNR, filing numbers, and daily orders",
          tag: "eCourts",
          tagColor: { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa" },
          action: () => {
            onClose();
            router.push("/court-tracking");
          },
        },
        {
          id: "dest-calendar",
          category: "Destination",
          title: "📅 Hearing Calendar & Deadlines",
          subtitle: "View today's listings, limitation radar, and scheduled hearings",
          tag: "Calendar",
          tagColor: { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24" },
          action: () => {
            onClose();
            router.push("/calendar");
          },
        },
        {
          id: "dest-documents",
          category: "Destination",
          title: "📁 Evidence & Document Vault",
          subtitle: "Access case filings, camera uploads, notices, and SHA-256 verified exhibits",
          tag: "Vault",
          tagColor: { bg: "rgba(16, 185, 129, 0.15)", text: "#34d399" },
          action: () => {
            onClose();
            router.push("/documents");
          },
        },
        {
          id: "dest-lawyers",
          category: "Destination",
          title: "🔍 Find Verified Advocates",
          subtitle: "Browse High Court & Supreme Court counsels with transparent pricing",
          tag: "Directory",
          tagColor: { bg: "rgba(99, 102, 241, 0.15)", text: "#818cf8" },
          action: () => {
            onClose();
            router.push("/lawyers");
          },
        }
      );
    } else {
      // Matching cases
      matchingCases.forEach((c) => {
        actions.push({
          id: `case-${c.id}`,
          category: "Case",
          title: c.title,
          subtitle: `REF #${c.id.slice(0, 8).toUpperCase()} • ${c.description?.slice(0, 60) || "Matter record"}`,
          tag: c.status || "MATTER",
          tagColor: {
            bg: c.status === "OPEN" ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.15)",
            text: c.status === "OPEN" ? "#10b981" : "#60a5fa",
          },
          action: () => {
            saveRecentSearch(query);
            onClose();
            router.push(`/cases/${c.id}`);
          },
        });
      });

      // Matching lawyers
      matchingLawyers.forEach((l) => {
        actions.push({
          id: `lawyer-${l.id}`,
          category: "Lawyer",
          title: l.full_name,
          subtitle: `📍 ${l.location || "India"} • ${l.experience_years ? `${l.experience_years} Yrs at Bar` : "Counsel"}`,
          tag: "Advocate",
          tagColor: { bg: "rgba(109, 124, 255, 0.15)", text: "#8d98ff" },
          action: () => {
            saveRecentSearch(query);
            onClose();
            router.push(`/lawyers?search=${encodeURIComponent(query)}`);
          },
        });
      });

      // Matching court records
      matchingCourtCases.forEach((cc) => {
        actions.push({
          id: `court-${cc.id}`,
          category: "Court Record",
          title: `${cc.petitioner} v. ${cc.respondent}`,
          subtitle: `${cc.court_name} • CNR: ${cc.cnr || "N/A"} • ${cc.human_status || cc.technical_status}`,
          tag: "OFFICIAL COURT DATA",
          tagColor: { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa" },
          action: () => {
            saveRecentSearch(query);
            onClose();
            router.push(`/court-tracking?cnr=${cc.cnr || cc.id}`);
          },
        });
      });
    }

    return actions;
  }, [query, recentSearches, matchingCases, matchingLawyers, matchingCourtCases, onClose, router, saveRecentSearch]);

  // Keyboard navigation listener (ArrowUp, ArrowDown, Enter, Escape)
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (resultActions.length > 0 ? (prev + 1) % resultActions.length : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (resultActions.length > 0 ? (prev - 1 + resultActions.length) % resultActions.length : 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (resultActions[selectedIndex]) {
          resultActions[selectedIndex].action();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, resultActions, selectedIndex]);

  if (!isOpen) return null;

  return (
    <div className={styles.searchOverlay} onClick={onClose}>
      <div
        className={styles.searchDialog}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Global Search"
      >
        <div className={styles.inputRow}>
          <span className={styles.searchIcon} aria-hidden="true">
            🔍
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search cases, hearings, documents, or verified advocates... (↑↓ to navigate)"
            className={styles.searchInput}
            aria-autocomplete="list"
          />
          <span className={styles.escBadge} onClick={onClose} style={{ cursor: "pointer" }}>
            ESC
          </span>
        </div>

        <div className={styles.resultsList} role="listbox">
          {searching ? (
            <div className={styles.emptyResults}>Searching authorized matters and legal directory...</div>
          ) : query.length >= 2 && resultActions.length === 0 ? (
            <div className={styles.emptyResults}>
              No matching cases, hearings, documents, or advocates found for &quot;{query}&quot;.
            </div>
          ) : (
            resultActions.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  role="option"
                  aria-selected={isSelected}
                  className={`${styles.resultItem} ${isSelected ? styles.resultItemActive : ""}`}
                  onClick={item.action}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <div className={styles.resultMain}>
                    <div className={styles.resultTitle}>{item.title}</div>
                    <div className={styles.resultSub}>{item.subtitle}</div>
                  </div>
                  <span
                    className={styles.resultTag}
                    style={{
                      background: item.tagColor.bg,
                      color: item.tagColor.text,
                    }}
                  >
                    {item.tag}
                  </span>
                </div>
              );
            })
          )}
        </div>

        <div className={styles.footerBar}>
          <span>Use ↑ ↓ to navigate, Enter to select, ESC to exit</span>
          <span>⚡ Scoped to authenticated permissions</span>
        </div>
      </div>
    </div>
  );
}

export default GlobalSearchModal;
