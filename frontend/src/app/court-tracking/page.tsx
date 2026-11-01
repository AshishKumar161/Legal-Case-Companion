"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/api/client";
import LegalTerm from "@/components/LegalTerm";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { trackFunnelEvent } from "@/lib/analytics";
import { CourtCaseSummary, CourtCaseDetail } from "@/types";
import {
  CourthouseIcon,
  DocumentIcon,
  DownloadIcon,
  ClockIcon,
  CheckCircleIcon,
} from "@/components/ui/Icons";
import styles from "./page.module.css";

type SearchMode = "cnr" | "case_no" | "party" | "advocate";
type DetailTab = "history" | "causelist" | "orders" | "parties";

export default function CourtTrackingPage() {
  const [searchMode, setSearchMode] = useState<SearchMode>("cnr");
  const [searchInput, setSearchInput] = useState("DLHC010041202025");
  const [selectedCourt, setSelectedCourt] = useState("all");
  const [selectedYear, setSelectedYear] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Results & Detail State
  const [results, setResults] = useState<CourtCaseSummary[]>([]);
  const [activeCase, setActiveCase] = useState<CourtCaseDetail | null>(null);
  const [activeDetailTab, setActiveDetailTab] = useState<DetailTab>("history");

  // Loading & Error States
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch Full Case Detail
  const fetchCaseDetail = useCallback(async (idOrCnr: string) => {
    setIsLoadingDetail(true);
    setActionNotice(null);
    try {
      const data = await apiClient.get(`/api/v1/court-cases/${encodeURIComponent(idOrCnr)}`);
      setActiveCase(data as CourtCaseDetail);
      trackFunnelEvent("court_result_opened", { court_category: (data as CourtCaseDetail).court_name });
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Unable to retrieve case details.";
      setError(msg);
    } finally {
      setIsLoadingDetail(false);
    }
  }, []);

  // Execute Search
  const executeSearch = useCallback(
    async (queryText: string, mode: SearchMode, courtFilter: string, yearFilter: string) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      setIsSearching(true);
      setError(null);
      trackFunnelEvent("court_search_started", { intent: mode });

      try {
        const params = new URLSearchParams();
        if (queryText.trim()) params.set("search", queryText.trim());
        params.set("mode", mode);
        if (courtFilter && courtFilter !== "all") params.set("court", courtFilter);
        if (yearFilter && yearFilter.trim()) params.set("year", yearFilter.trim());
        params.set("limit", "20");

        const data = await apiClient.get(`/api/v1/court-cases?${params.toString()}`);
        const items: CourtCaseSummary[] = Array.isArray(data) ? data : [];
        setResults(items);
        trackFunnelEvent("court_search_completed", { results_count: items.length });

        // Auto-select first result if only 1 matching record
        if (items.length === 1 && !activeCase) {
          fetchCaseDetail(items[0].cnr);
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        const msg = err instanceof ApiError ? err.message : "Unable to load court records. Please check your connection.";
        setError(msg);
      } finally {
        setIsSearching(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fetchCaseDetail]
  );

  // Initial load
  useEffect(() => {
    executeSearch("DLHC010041202025", "cnr", "all", "");
    fetchCaseDetail("DLHC010041202025");
  }, [executeSearch, fetchCaseDetail]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveCase(null);
    executeSearch(searchInput, searchMode, selectedCourt, selectedYear);
  };

  // Explicit Sync
  const handleSync = async () => {
    if (!activeCase) return;
    setIsSyncing(true);
    setActionNotice(null);
    try {
      const res = (await apiClient.post(`/api/v1/court-cases/${activeCase.id}/sync`, {})) as {
        last_synchronized_at: string;
        sync_status: string;
        message: string;
      };
      setActiveCase((prev) =>
        prev
          ? {
              ...prev,
              last_synchronized_at: res.last_synchronized_at,
              sync_status: res.sync_status,
            }
          : null
      );
      setActionNotice(res.message);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Synchronization failed.";
      setError(msg);
    } finally {
      setIsSyncing(false);
    }
  };

  // Follow / Unfollow Case
  const handleToggleFollow = async () => {
    if (!activeCase) return;
    try {
      if (activeCase.is_followed) {
        await apiClient.delete(`/api/v1/court-cases/${activeCase.id}/follow`);
        setActiveCase((prev) => (prev ? { ...prev, is_followed: false } : null));
        setActionNotice(`Unfollowed ${activeCase.case_number}.`);
      } else {
        await apiClient.post(`/api/v1/court-cases/${activeCase.id}/follow`, {});
        setActiveCase((prev) => (prev ? { ...prev, is_followed: true } : null));
        setActionNotice(`You are now following official updates for ${activeCase.case_number}.`);
        trackFunnelEvent("case_followed", { has_case_link: Boolean(activeCase.case_id) });
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Unable to update follow status.";
      setError(msg);
    }
  };

  // Link / Create Matter
  const handleLinkMatter = async () => {
    if (!activeCase) return;
    try {
      const res = (await apiClient.post(`/api/v1/court-cases/${activeCase.id}/link-matter`, {})) as {
        case_id: string;
        message: string;
      };
      setActiveCase((prev) => (prev ? { ...prev, case_id: res.case_id } : null));
      setActionNotice("Court case successfully linked to LCC Matter Workspace.");
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Unable to link matter workspace.";
      setError(msg);
    }
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.eyebrow}>
          <CourthouseIcon size={14} color="#2563eb" />
          <span>eCourts & Cause List Ecosystem</span>
        </div>
        <h1 className={styles.title}>Find your case</h1>
        <p className={styles.subtitle}>
          Track litigation records, hearing dates, daily cause lists, and orders across Indian High Courts and District Courts with plain-language explanations.
        </p>

        {/* Pilot Jurisdiction & Provenance Notice Banner */}
        <div className={styles.disclaimerBanner}>
          <div>
            <div style={{ fontWeight: 700, color: "#1e40af", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
              <CourthouseIcon size={15} color="#2563eb" />
              <span>Active Pilot Jurisdictions: High Court of Delhi, High Court of Bombay, and High Court of Allahabad. (District courts expanding in Cohort 2).</span>
            </div>
            <strong>Important Notice on Court Records:</strong> Legal Case Companion tracks publicly available court information for matter governance. LCC is an independent legal management platform and does not replace official court records. Certified copies must be obtained from the respective court registry.
          </div>
          <div className={styles.syncBadge}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981" }} />
            Sync Status: Online (IST)
          </div>
        </div>
      </header>

      {/* Search Card */}
      <div className={styles.searchCard}>
        <div className={styles.tabRow} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={searchMode === "cnr"}
            className={`${styles.tabBtn} ${searchMode === "cnr" ? styles.tabBtnActive : ""}`}
            onClick={() => {
              setSearchMode("cnr");
              setSearchInput("DLHC010041202025");
            }}
          >
            Search by CNR
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={searchMode === "case_no"}
            className={`${styles.tabBtn} ${searchMode === "case_no" ? styles.tabBtnActive : ""}`}
            onClick={() => {
              setSearchMode("case_no");
              setSearchInput("412/2025");
            }}
          >
            Case Number
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={searchMode === "party"}
            className={`${styles.tabBtn} ${searchMode === "party" ? styles.tabBtnActive : ""}`}
            onClick={() => {
              setSearchMode("party");
              setSearchInput("Sharma Estates");
            }}
          >
            Party Name
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={searchMode === "advocate"}
            className={`${styles.tabBtn} ${searchMode === "advocate" ? styles.tabBtnActive : ""}`}
            onClick={() => {
              setSearchMode("advocate");
              setSearchInput("Vikramaditya Sen");
            }}
          >
            Advocate Name
          </button>
        </div>

        <form className={styles.searchForm} onSubmit={handleSearchSubmit}>
          <div className={styles.inputGroup}>
            <label className={styles.label} htmlFor="courtSearchInput">
              {searchMode === "cnr" && "16-Digit CNR Number (Case National Reference)"}
              {searchMode === "case_no" && "Case Number / Filing Number"}
              {searchMode === "party" && "Petitioner or Respondent Name"}
              {searchMode === "advocate" && "Advocate Name"}
            </label>
            <input
              id="courtSearchInput"
              className={`${styles.input} ${searchMode === "cnr" ? styles.monoInput : ""}`}
              placeholder={
                searchMode === "cnr"
                  ? "e.g. DLHC010041202025"
                  : searchMode === "case_no"
                  ? "e.g. CS(COMM) 412/2025 or 18942/2025"
                  : searchMode === "party"
                  ? "e.g. Sharma Estates or Mehta Trading"
                  : "e.g. Vikramaditya Sen or Ananya Roy"
              }
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              required
            />
            {searchMode === "cnr" && (
              <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Tip: The CNR is a unique 16-character alphanumeric code printed on your summons, petition, or eCourts receipt.
              </span>
            )}
          </div>

          {/* Progressive Disclosure: Advanced Search */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                background: "transparent",
                border: "none",
                color: "#2563eb",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                padding: "4px 0",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <span>{showAdvanced ? "▲ Hide Advanced Filters" : "▼ Show Advanced Filters (Court, Year)"}</span>
            </button>
          </div>

          {showAdvanced && (
            <div className={styles.inputGrid}>
              <div className={styles.inputGroup}>
                <label className={styles.label} htmlFor="courtSelect">Select Court</label>
                <select
                  id="courtSelect"
                  className={styles.select}
                  value={selectedCourt}
                  onChange={(e) => setSelectedCourt(e.target.value)}
                >
                  <option value="all">All Courts</option>
                  <option value="delhi_hc">Delhi High Court</option>
                  <option value="bombay_hc">Bombay High Court</option>
                  <option value="calcutta_hc">Calcutta High Court</option>
                  <option value="madras_hc">Madras High Court</option>
                  <option value="karnataka_hc">Karnataka High Court</option>
                  <option value="tis_hazari">District Court (Tis Hazari, Delhi)</option>
                  <option value="saket">District Court (Saket, Delhi)</option>
                </select>
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label} htmlFor="caseYearInput">Filing / Registration Year</label>
                <input
                  id="caseYearInput"
                  className={styles.input}
                  placeholder="e.g. 2026"
                  value={selectedYear}
                  onChange={(e) => setSelectedYear(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className={styles.searchActionRow}>
            <button type="submit" className={styles.searchBtn} disabled={isSearching}>
              {isSearching ? "Searching Records..." : "Search Court Records"}
            </button>
          </div>
        </form>
      </div>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div
          style={{
            background: "#ecfdf5",
            border: "1px solid #a7f3d0",
            color: "#059669",
            padding: "10px 16px",
            borderRadius: "8px",
            marginBottom: "20px",
            fontSize: "13px",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <CheckCircleIcon size={16} color="#059669" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#dc2626",
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "20px",
            fontSize: "13px",
            fontWeight: 500,
          }}
        >
          {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {(isSearching || isLoadingDetail) && (
        <div style={{ marginBottom: "32px" }}>
          <LoadingSkeleton type="card" count={2} />
        </div>
      )}

      {/* Search Results Summary List (when multiple results or browsing) */}
      {!isSearching && results.length > 1 && (
        <div className={styles.resultsList}>
          <div style={{ fontSize: "14px", fontWeight: 700, color: "#334155" }}>
            Found {results.length} court records matching your search:
          </div>
          {results.map((item) => (
            <div
              key={item.id}
              className={styles.summaryCard}
              onClick={() => fetchCaseDetail(item.id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <span className={styles.cnrPill}>{item.cnr}</span>
                <span className={styles.provenanceBadge}>{item.source_provenance}</span>
              </div>
              <h3 style={{ margin: 0, fontSize: "17px", fontWeight: 700, color: "#0f172a" }}>
                {item.petitioner} v. {item.respondent}
              </h3>
              <div style={{ fontSize: "13px", color: "#64748b" }}>
                {item.court_name} · <strong>{item.case_number}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", paddingTop: "8px", borderTop: "1px solid #e2e8f0" }}>
                <LegalTerm term={item.technical_status} source={item.source_provenance} />
                <span style={{ fontSize: "12px", color: "#2563eb", fontWeight: 600 }}>
                  View Complete Record →
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No Results Empty State */}
      {!isSearching && results.length === 0 && (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <CourthouseIcon size={24} color="#2563eb" />
          </div>
          <h2 className={styles.emptyTitle}>We couldn&apos;t find a case matching those details.</h2>
          <p className={styles.emptyDesc}>
            Check the number or name and try again. You can search by 16-digit CNR, case number (e.g. 412/2025), party name, or advocate name.
          </p>
          <button
            type="button"
            className={styles.secondaryBtn}
            onClick={() => {
              setSearchMode("cnr");
              setSearchInput("DLHC010041202025");
              setSelectedCourt("all");
              setSelectedYear("");
              executeSearch("DLHC010041202025", "cnr", "all", "");
            }}
          >
            Reset Search
          </button>
        </div>
      )}

      {/* Authoritative Case Detail Card */}
      {activeCase && !isLoadingDetail && (
        <div className={styles.resultCard}>
          {/* Top Bar: Provenance, Sync, Actions */}
          <div className={styles.resultTopBar}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <span className={styles.provenanceBadge}>
                <CourthouseIcon size={14} color="#065f46" /> {activeCase.source_provenance}
              </span>
              <span style={{ fontSize: "12px", color: "#64748b" }}>
                Last synchronized: {new Date(activeCase.last_synchronized_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })} · {new Date(activeCase.last_synchronized_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} IST
              </span>
            </div>

            <div className={styles.actionBtnGroup}>
              <button
                type="button"
                className={`${styles.followBtn} ${activeCase.is_followed ? styles.followBtnActive : ""}`}
                onClick={handleToggleFollow}
              >
                {activeCase.is_followed ? "Following Updates ✓" : "+ Follow Case"}
              </button>

              <button
                type="button"
                className={styles.secondaryBtn}
                onClick={handleSync}
                disabled={isSyncing}
              >
                <ClockIcon size={14} color="#334155" />
                <span>{isSyncing ? "Syncing Registry..." : "Sync Registry"}</span>
              </button>
            </div>
          </div>

          {/* Case Header */}
          <div className={styles.caseHeaderSection}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px", flexWrap: "wrap" }}>
                  <span className={styles.cnrPill}>CNR: {activeCase.cnr}</span>
                  {activeCase.case_id ? (
                    <Link href={`/cases/${activeCase.case_id}`} className={styles.matterLinkBadge}>
                      ✓ Linked to Matter Workspace →
                    </Link>
                  ) : (
                    <button type="button" onClick={handleLinkMatter} className={styles.matterLinkBadge} style={{ cursor: "pointer" }}>
                      + Import to My Matters
                    </button>
                  )}
                </div>
                <h2 className={styles.caseTitle}>
                  {activeCase.petitioner} v. {activeCase.respondent}
                </h2>
              </div>
            </div>

            <div className={styles.caseMetaRow}>
              <span>Court: <strong>{activeCase.court_name}</strong></span>
              <span>Case Number: <strong>{activeCase.case_number}</strong></span>
              {activeCase.filing_number && <span>Filing No: <strong>{activeCase.filing_number}</strong></span>}
              {activeCase.filing_date && <span>Filed: <strong>{activeCase.filing_date}</strong></span>}
            </div>

            {/* 3-Layer Status Box with LegalTerm */}
            <div className={styles.statusCallout}>
              <div className={styles.statusLayerText}>
                <LegalTerm
                  term={activeCase.technical_status}
                  source={activeCase.source_provenance}
                  showTechnicalSubtitle={true}
                  layout="stacked"
                />
                <div style={{ marginTop: "6px", fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  {activeCase.human_status}
                </div>
              </div>

              {activeCase.next_hearing_date && (
                <div style={{ background: "var(--surface-card, #ffffff)", padding: "12px 16px", borderRadius: "8px", border: "1px solid var(--border-subtle, #e2e8f0)", boxShadow: "var(--shadow-sm)" }}>
                  <div style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: 700, color: "#2563eb", display: "flex", alignItems: "center", gap: "4px" }}>
                    <ClockIcon size={12} color="#2563eb" />
                    <span>Next Important Date</span>
                  </div>
                  <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary, #0f172a)", marginTop: "4px" }}>
                    {new Date(activeCase.next_hearing_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                    {activeCase.next_hearing_purpose}
                  </div>
                </div>
              )}
            </div>

            {/* Milestone Guidance: What Happens Next? */}
            <div style={{ marginTop: "16px", padding: "14px 18px", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "8px", fontSize: "13px", color: "#1e3a8a", lineHeight: 1.5 }}>
              <strong style={{ color: "#1e40af" }}>What happens next?</strong>{" "}
              {activeCase.technical_status.toLowerCase().includes("reserved")
                ? "The scheduled hearing has taken place. All oral submissions have concluded. The court will pronounce the final order or judgment on the listed date. No further oral appearances are required."
                : activeCase.technical_status.toLowerCase().includes("notice")
                ? "Court notice has been issued. The opposite party is granted time to submit their formal written statement."
                : "Your case is actively progressing on the court board. Your counsel will appear on the listed date."}
            </div>
          </div>

          {/* Details Grid: Bench, Room, Acts */}
          <div className={styles.detailsGrid}>
            <div className={styles.detailCol}>
              <div className={styles.detailLabel}>Coram / Bench</div>
              <div className={styles.detailValue}>{activeCase.bench || "Single Judge Bench"}</div>
              <div className={styles.detailSub}>
                {activeCase.court_room ? `${activeCase.court_room} · ${activeCase.item_number || "Item Listed"}` : "Court Room details in Cause List"}
              </div>
            </div>

            <div className={styles.detailCol}>
              <div className={styles.detailLabel}>Petitioner & Counsel</div>
              <div className={styles.detailValue}>{activeCase.petitioner}</div>
              <div className={styles.detailSub}>{activeCase.petitioner_advocate || "Advocate on Record"}</div>
            </div>

            <div className={styles.detailCol}>
              <div className={styles.detailLabel}>Respondent & Counsel</div>
              <div className={styles.detailValue}>{activeCase.respondent}</div>
              <div className={styles.detailSub}>{activeCase.respondent_advocate || "Standing Counsel / Vakalatnama on file"}</div>
            </div>
          </div>

          {/* Sub-Tabs: History, Cause List, Orders */}
          <div className={styles.subTabs} role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeDetailTab === "history"}
              className={`${styles.tabBtn} ${activeDetailTab === "history" ? styles.tabBtnActive : ""}`}
              onClick={() => setActiveDetailTab("history")}
            >
              Hearing History ({activeCase.history.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeDetailTab === "causelist"}
              className={`${styles.tabBtn} ${activeDetailTab === "causelist" ? styles.tabBtnActive : ""}`}
              onClick={() => setActiveDetailTab("causelist")}
            >
              Daily Cause List
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeDetailTab === "orders"}
              className={`${styles.tabBtn} ${activeDetailTab === "orders" ? styles.tabBtnActive : ""}`}
              onClick={() => setActiveDetailTab("orders")}
            >
              Orders & Judgments ({activeCase.orders.length})
            </button>
          </div>

          {/* Tab 1: Hearing History */}
          {activeDetailTab === "history" && (
            <div style={{ overflowX: "auto" }}>
              <table className={styles.historyTable}>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Coram / Judge</th>
                    <th>Court Proceedings Recorded</th>
                    <th>Next Date</th>
                  </tr>
                </thead>
                <tbody>
                  {activeCase.history.map((h, idx) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600, color: "#0f172a", whiteSpace: "nowrap" }}>{h.date}</td>
                      <td>{h.judge}</td>
                      <td>{h.business}</td>
                      <td style={{ fontWeight: 600, color: "#2563eb", whiteSpace: "nowrap" }}>
                        {h.next_date || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 2: Daily Cause List */}
          {activeDetailTab === "causelist" && activeCase.cause_list && (
            <div style={{ padding: "24px" }}>
              <div style={{ background: "var(--surface-card, #ffffff)", border: "1px solid var(--border-subtle, #e2e8f0)", borderRadius: "10px", padding: "20px", boxShadow: "var(--shadow-sm)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "8px" }}>
                  <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
                    Daily Board: {activeCase.cause_list.cause_list_date}
                  </div>
                  <span className={styles.provenanceBadge}>Official Registry Cause List</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", fontSize: "13px" }}>
                  <div>
                    <span style={{ color: "#64748b", display: "block", marginBottom: "4px" }}>Court Room:</span>
                    <strong style={{ color: "#0f172a", fontSize: "15px" }}>{activeCase.cause_list.court_room}</strong>
                  </div>
                  <div>
                    <span style={{ color: "#64748b", display: "block", marginBottom: "4px" }}>Item Number:</span>
                    <strong style={{ color: "#0f172a", fontSize: "15px" }}>{activeCase.cause_list.item_number}</strong>
                  </div>
                  <div>
                    <span style={{ color: "#64748b", display: "block", marginBottom: "4px" }}>Bench:</span>
                    <strong style={{ color: "#0f172a" }}>{activeCase.cause_list.bench}</strong>
                  </div>
                  <div>
                    <span style={{ color: "#64748b", display: "block", marginBottom: "4px" }}>Listing Purpose:</span>
                    <strong style={{ color: "#059669" }}>{activeCase.cause_list.board_status}</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 3: Orders & Judgments */}
          {activeDetailTab === "orders" && (
            <div style={{ padding: "24px" }}>
              {activeCase.orders.length === 0 ? (
                <div style={{ color: "#64748b", textAlign: "center", padding: "24px" }}>
                  No interim orders or judgments uploaded for this matter yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {activeCase.orders.map((ord, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: "var(--surface-card, #ffffff)",
                        border: "1px solid var(--border-subtle, #e2e8f0)",
                        borderRadius: "8px",
                        padding: "16px 20px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: "12px",
                        boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <DocumentIcon size={16} color="#2563eb" />
                          <span>{ord.title}</span>
                        </div>
                        <div style={{ fontSize: "12px", color: "#64748b" }}>
                          Order Date: {ord.order_date} · {ord.pages} Pages · SHA-256: <code style={{ fontSize: "11px", background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px", color: "#334155" }}>{ord.sha256.slice(0, 16)}...</code>
                        </div>
                      </div>

                      <button
                        type="button"
                        className={styles.secondaryBtn}
                        onClick={() => {
                          trackFunnelEvent("order_opened", { court_category: ord.title });
                          alert(`Secure certified copy hash: ${ord.sha256}\nDocument title: ${ord.title}\nProtected under court verification protocol.`);
                        }}
                      >
                        <DownloadIcon size={14} color="#334155" />
                        <span>Download Order</span>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
