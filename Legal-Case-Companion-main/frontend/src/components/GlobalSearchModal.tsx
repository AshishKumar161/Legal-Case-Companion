"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import { CaseItem, LawyerProfileItem } from "@/types";
import styles from "./GlobalSearchModal.module.css";

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GlobalSearchModal({ isOpen, onClose }: GlobalSearchModalProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [matchingCases, setMatchingCases] = useState<CaseItem[]>([]);
  const [matchingLawyers, setMatchingLawyers] = useState<LawyerProfileItem[]>([]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
      setMatchingCases([]);
      setMatchingLawyers([]);
    }
  }, [isOpen]);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
      // Ctrl+K or Cmd+K shortcut
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (isOpen) onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Perform search across authorized cases & lawyer directory
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setMatchingCases([]);
      setMatchingLawyers([]);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const [casesRes, lawyersRes] = await Promise.all([
          apiClient.get(`/api/v1/cases?search=${encodeURIComponent(query.trim())}&limit=5`).catch(() => ({ items: [] })),
          apiClient.get(`/api/v1/lawyers?search=${encodeURIComponent(query.trim())}&limit=4`).catch(() => ({ items: [] })),
        ]);

        setMatchingCases(casesRes?.items || (Array.isArray(casesRes) ? casesRes : []));
        setMatchingLawyers(lawyersRes?.items || (Array.isArray(lawyersRes) ? lawyersRes : []));
      } catch (err) {
        console.error("Global search error:", err);
      } finally {
        setSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelectCase = (caseId: string) => {
    onClose();
    router.push(`/cases/${caseId}`);
  };

  const handleSelectLawyer = () => {
    onClose();
    router.push(`/lawyers?search=${encodeURIComponent(query)}`);
  };

  if (!isOpen) return null;

  return (
    <div className={styles.searchOverlay} onClick={onClose}>
      <div className={styles.searchDialog} onClick={(e) => e.stopPropagation()}>
        <div className={styles.inputRow}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search matters, documents, or verified advocates... (Type at least 2 characters)"
            className={styles.searchInput}
          />
          <span className={styles.escBadge}>ESC</span>
        </div>

        <div className={styles.resultsList}>
          {searching ? (
            <div className={styles.emptyResults}>Searching authorized matters and legal directory...</div>
          ) : query.length >= 2 && matchingCases.length === 0 && matchingLawyers.length === 0 ? (
            <div className={styles.emptyResults}>
              No matching matters or legal counsel found for &quot;{query}&quot;.
            </div>
          ) : query.length < 2 ? (
            <div className={styles.emptyResults}>
              Type matter caption, reference ID, legal issue, or advocate name to search.
            </div>
          ) : (
            <>
              {/* Cases Results */}
              {matchingCases.length > 0 && (
                <div>
                  <div className={styles.groupHeader}>Legal Matters ({matchingCases.length})</div>
                  {matchingCases.map((c) => (
                    <div
                      key={c.id}
                      className={styles.resultItem}
                      onClick={() => handleSelectCase(c.id)}
                    >
                      <div className={styles.resultMain}>
                        <div className={styles.resultTitle}>{c.title}</div>
                        <div className={styles.resultSub}>
                          REF #{c.id.slice(0, 8).toUpperCase()} • {c.description?.slice(0, 70) || "Matter record"}
                        </div>
                      </div>
                      <span
                        className={styles.resultTag}
                        style={{
                          background: c.status === "OPEN" ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.15)",
                          color: c.status === "OPEN" ? "#10b981" : "#60a5fa",
                        }}
                      >
                        {c.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Lawyers Results */}
              {matchingLawyers.length > 0 && (
                <div style={{ marginTop: matchingCases.length > 0 ? "8px" : "0" }}>
                  <div className={styles.groupHeader}>Verified Advocates ({matchingLawyers.length})</div>
                  {matchingLawyers.map((l) => (
                    <div
                      key={l.id}
                      className={styles.resultItem}
                      onClick={handleSelectLawyer}
                    >
                      <div className={styles.resultMain}>
                        <div className={styles.resultTitle}>{l.full_name}</div>
                        <div className={styles.resultSub}>
                          📍 {l.location || "India"} • {l.experience_years ? `${l.experience_years} Yrs at Bar` : "Counsel"}
                        </div>
                      </div>
                      <span
                        className={styles.resultTag}
                        style={{
                          background: "rgba(109, 124, 255, 0.15)",
                          color: "#8d98ff",
                        }}
                      >
                        Advocate
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className={styles.footerBar}>
          <span>Navigate with cursor or touch • Press ESC to close</span>
          <span>⚡ Scoped to your authenticated legal permissions</span>
        </div>
      </div>
    </div>
  );
}
