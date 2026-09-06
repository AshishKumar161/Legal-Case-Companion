"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/api/client";
import { ShareableParticipant, EvidenceAccessGrantItem } from "@/types";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";

interface EvidenceShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  evidenceId: string;
  evidenceTitle: string;
}

export function EvidenceShareModal({
  isOpen,
  onClose,
  caseId,
  evidenceId,
  evidenceTitle,
}: EvidenceShareModalProps) {
  const [participants, setParticipants] = useState<ShareableParticipant[]>([]);
  const [grants, setGrants] = useState<EvidenceAccessGrantItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sharing, setSharing] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [accessLevel, setAccessLevel] = useState<"VIEW" | "DOWNLOAD">("VIEW");
  const [expiresAt, setExpiresAt] = useState<string>("");

  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!isOpen || !caseId || !evidenceId) return;
    try {
      setLoading(true);
      setErrorMsg(null);

      const [partData, grantData] = await Promise.all([
        apiClient.get<ShareableParticipant[]>(
          `/api/v1/cases/${caseId}/evidence/${evidenceId}/shareable-participants`
        ),
        apiClient.get<EvidenceAccessGrantItem[]>(
          `/api/v1/cases/${caseId}/evidence/${evidenceId}/grants`
        ),
      ]);

      setParticipants(Array.isArray(partData) ? partData : []);
      setGrants(Array.isArray(grantData) ? grantData : []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load participant or grant data.";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  }, [isOpen, caseId, evidenceId]);

  useEffect(() => {
    if (isOpen) {
      setSuccessMsg(null);
      setErrorMsg(null);
      setSelectedUserId("");
      setExpiresAt("");
      void loadData();
    }
  }, [isOpen, loadData]);

  const handleShare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUserId) {
      setErrorMsg("Please select a case participant to share with.");
      return;
    }

    try {
      setSharing(true);
      setErrorMsg(null);
      setSuccessMsg(null);

      const payload: {
        target_user_id: string;
        access_level: "VIEW" | "DOWNLOAD";
        expires_at?: string;
      } = {
        target_user_id: selectedUserId,
        access_level: accessLevel,
      };

      if (expiresAt) {
        payload.expires_at = new Date(expiresAt).toISOString();
      }

      await apiClient.post(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/share`,
        payload
      );

      setSuccessMsg("Document access successfully granted.");
      setSelectedUserId("");
      setExpiresAt("");
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to grant document access.";
      setErrorMsg(msg);
    } finally {
      setSharing(false);
    }
  };

  const handleRevoke = async (targetUserId: string) => {
    try {
      setRevokingId(targetUserId);
      setErrorMsg(null);
      setSuccessMsg(null);

      await apiClient.post(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/revoke`,
        {
          target_user_id: targetUserId,
          reason: "Revoked by case manager",
        }
      );

      setSuccessMsg("Access grant successfully revoked.");
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke access grant.";
      setErrorMsg(msg);
    } finally {
      setRevokingId(null);
    }
  };

  const activeGrants = grants.filter((g) => !g.revoked_at);

  const participantOptions = [
    { value: "", label: "Select an authorized participant..." },
    ...participants.map((p) => ({
      value: p.user_id,
      label: `${p.full_name} (${p.role}) — ${p.email}${p.has_access ? " ✓ (Active Access)" : ""}`,
    })),
  ];

  const accessLevelOptions = [
    { value: "VIEW", label: "View Only (Preview in Browser)" },
    { value: "DOWNLOAD", label: "View & Download (Presigned S3 URL)" },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Share Document"
      description={`Manage secure access permissions for "${evidenceTitle}"`}
      size="lg"
      footer={
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button variant="secondary" size="md" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {errorMsg && (
          <Alert variant="urgent" onDismiss={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {successMsg && (
          <Alert variant="success" onDismiss={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {/* Share Form Card */}
        <div
          style={{
            background: "var(--surface-subtle, #141824)",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
            borderRadius: "10px",
            padding: "20px",
          }}
        >
          <div
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "var(--text-primary, #f8fafc)",
              marginBottom: "14px",
            }}
          >
            Grant Access to Case Participant
          </div>

          <form onSubmit={handleShare} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <Select
                label="Case Participant"
                options={participantOptions}
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                disabled={loading || sharing}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
              <div>
                <Select
                  label="Access Permission Level"
                  options={accessLevelOptions}
                  value={accessLevel}
                  onChange={(e) => setAccessLevel(e.target.value as "VIEW" | "DOWNLOAD")}
                  disabled={loading || sharing}
                />
              </div>

              <div>
                <label
                  style={{
                    display: "block",
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "var(--text-secondary, #94a3b8)",
                    marginBottom: "6px",
                  }}
                >
                  Access Expiration (Optional)
                </label>
                <Input
                  type="date"
                  value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)}
                  disabled={loading || sharing}
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "4px" }}>
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={sharing}
                disabled={loading || !selectedUserId}
              >
                Grant Access
              </Button>
            </div>
          </form>
        </div>

        {/* Active Access Grants List */}
        <div>
          <div
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "var(--text-primary, #f8fafc)",
              marginBottom: "10px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <span>Active Access Grants</span>
            <span
              style={{
                fontSize: "11px",
                padding: "2px 8px",
                borderRadius: "10px",
                background: "rgba(255, 255, 255, 0.08)",
                color: "var(--text-muted, #64748b)",
              }}
            >
              {activeGrants.length}
            </span>
          </div>

          {loading ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)" }}>
              Loading access grants...
            </div>
          ) : activeGrants.length === 0 ? (
            <EmptyState
              title="No active grants"
              description="This document has not been shared with any additional case participants yet."
              style={{ padding: "24px" }}
            />
          ) : (
            <div
              style={{
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: "8px",
                overflow: "hidden",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr
                    style={{
                      background: "var(--surface-elevated, #151A24)",
                      borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                      textAlign: "left",
                      color: "var(--text-secondary, #94a3b8)",
                    }}
                  >
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Recipient</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Level</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Granted On</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Expires</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {activeGrants.map((g) => (
                    <tr
                      key={g.id}
                      style={{
                        borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.04))",
                      }}
                    >
                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                          {g.grantee_name || "Authorized Participant"}
                        </div>
                        {g.grantee_email && (
                          <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{g.grantee_email}</div>
                        )}
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <Badge variant={g.access_level === "DOWNLOAD" ? "primary" : "default"} size="sm">
                          {g.access_level}
                        </Badge>
                      </td>
                      <td style={{ padding: "12px 14px", color: "var(--text-secondary)" }}>
                        {new Date(g.created_at).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </td>
                      <td style={{ padding: "12px 14px", color: "var(--text-secondary)" }}>
                        {g.expires_at
                          ? new Date(g.expires_at).toLocaleDateString("en-IN", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })
                          : "No Expiration"}
                      </td>
                      <td style={{ padding: "12px 14px", textAlign: "right" }}>
                        <Button
                          variant="danger"
                          size="sm"
                          isLoading={revokingId === g.grantee_user_id}
                          disabled={revokingId !== null}
                          onClick={() => handleRevoke(g.grantee_user_id)}
                        >
                          Revoke
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
