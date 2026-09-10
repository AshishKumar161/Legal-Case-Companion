"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import { ClientProfileItem, LawyerProfileItem, NotificationPreferenceItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import styles from "./settings.module.css";
import Link from "next/link";

type SettingsTab = "profile" | "security" | "notifications";

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");
  const [fetching, setFetching] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);

  // Success & Error feedback
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [prefSuccess, setPrefSuccess] = useState<string | null>(null);
  const [prefError, setPrefError] = useState<string | null>(null);

  // Profile Form State
  const [profile, setProfile] = useState<ClientProfileItem | LawyerProfileItem | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [bio, setBio] = useState("");
  const [fee, setFee] = useState<number | string>("");
  const [experience, setExperience] = useState<number | string>("");
  const [practiceAreas, setPracticeAreas] = useState("");
  const [courtJurisdictions, setCourtJurisdictions] = useState("");

  // Password Form State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Notification Preferences State
  const [preferences, setPreferences] = useState<NotificationPreferenceItem>({
    email_enabled: true,
    case_updates: true,
    task_updates: true,
    consultation_updates: true,
  });

  const fetchSettingsData = useCallback(async () => {
    try {
      setFetching(true);
      const [profileRes, prefRes] = await Promise.all([
        apiClient.get("/api/v1/profiles/me").catch(() => null),
        apiClient.get("/api/v1/notifications/preferences").catch(() => null),
      ]);

      if (profileRes) {
        setProfile(profileRes);
        setFullName(profileRes.full_name || "");
        setPhone(profileRes.phone || "");
        setLocation(profileRes.location || "");
        if ("bio" in profileRes) setBio(profileRes.bio || "");
        if ("consultation_fee" in profileRes && profileRes.consultation_fee !== null) {
          setFee(profileRes.consultation_fee);
        }
        if ("experience_years" in profileRes && profileRes.experience_years !== null) {
          setExperience(profileRes.experience_years);
        }
        if ("practice_areas" in profileRes && profileRes.practice_areas) {
          setPracticeAreas(
            Array.isArray(profileRes.practice_areas)
              ? profileRes.practice_areas.join(", ")
              : String(profileRes.practice_areas)
          );
        }
        if ("court_jurisdictions" in profileRes && profileRes.court_jurisdictions) {
          setCourtJurisdictions(
            Array.isArray(profileRes.court_jurisdictions)
              ? profileRes.court_jurisdictions.join(", ")
              : String(profileRes.court_jurisdictions)
          );
        }
      }

      if (prefRes) {
        setPreferences({
          email_enabled: prefRes.email_enabled ?? true,
          case_updates: prefRes.case_updates ?? true,
          task_updates: prefRes.task_updates ?? true,
          consultation_updates: prefRes.consultation_updates ?? true,
        });
      }
    } catch (err) {
      console.error("Failed to load settings:", err);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    } else if (user) {
      void fetchSettingsData();
    }
  }, [user, authLoading, router, fetchSettingsData]);

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setProfileSuccess(null);
    setProfileError(null);

    try {
      if (user?.role === "CLIENT") {
        const payload = {
          full_name: fullName.trim() || undefined,
          location: location.trim() || undefined,
          phone: phone.trim() || undefined,
        };
        const updated = await apiClient.patch("/api/v1/profiles/client", payload);
        setProfile(updated);
        setProfileSuccess("Client profile details updated successfully.");
      } else if (user?.role === "LAWYER") {
        const pAreas = practiceAreas
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        const cJuris = courtJurisdictions
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

        const payload = {
          full_name: fullName.trim() || undefined,
          location: location.trim() || undefined,
          phone: phone.trim() || undefined,
          bio: bio.trim() || undefined,
          consultation_fee: fee !== "" ? Number(fee) : undefined,
          experience_years: experience !== "" ? Number(experience) : undefined,
          practice_areas: pAreas.length > 0 ? pAreas : undefined,
          court_jurisdictions: cJuris.length > 0 ? cJuris : undefined,
        };
        const updated = await apiClient.patch("/api/v1/profiles/lawyer", payload);
        setProfile(updated);
        setProfileSuccess("Advocate professional profile updated successfully.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile";
      setProfileError(msg);
    } finally {
      setSavingProfile(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordSuccess(null);
    setPasswordError(null);

    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }

    setSavingPassword(true);
    try {
      await apiClient.post("/api/v1/auth/password/change", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess("Password updated successfully. Other active sessions have been invalidated.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update password";
      setPasswordError(msg);
    } finally {
      setSavingPassword(false);
    }
  };

  const handlePrefToggle = async (key: keyof NotificationPreferenceItem, value: boolean) => {
    const updated = { ...preferences, [key]: value };
    setPreferences(updated);
    setSavingPrefs(true);
    setPrefSuccess(null);
    setPrefError(null);

    try {
      await apiClient.patch("/api/v1/notifications/preferences", { [key]: value });
      setPrefSuccess("Notification preferences updated.");
      setTimeout(() => setPrefSuccess(null), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update preference";
      setPrefError(msg);
    } finally {
      setSavingPrefs(false);
    }
  };

  if (authLoading || fetching || !user) {
    return (
      <div className={styles.settingsContainer}>
        <div className="container">
          <LoadingSkeleton type="card" count={2} />
        </div>
      </div>
    );
  }

  const isLawyer = user.role === "LAWYER";

  return (
    <div className={styles.settingsContainer}>
      <div className="container">
        {/* Header */}
        <div className={styles.headerSection}>
          <div className={styles.badgeCategory}>
            <span>●</span> Account & Preferences Management
          </div>
          <h1 className={styles.pageTitle}>Account Settings</h1>
          <p className={styles.pageSubtitle}>
            Manage your personal profile, secure Ed25519 authentication credentials, statutory jurisdiction records, and notification delivery channels.
          </p>
        </div>

        {/* Layout Grid */}
        <div className={styles.mainGrid}>
          {/* Navigation Sidebar */}
          <nav className={styles.navCard}>
            <button
              onClick={() => setActiveTab("profile")}
              className={`${styles.tabBtn} ${activeTab === "profile" ? styles.tabBtnActive : ""}`}
            >
              <span>👤</span>
              <span>Profile & Identity</span>
            </button>
            <button
              onClick={() => setActiveTab("security")}
              className={`${styles.tabBtn} ${activeTab === "security" ? styles.tabBtnActive : ""}`}
            >
              <span>🔒</span>
              <span>Security & Password</span>
            </button>
            <button
              onClick={() => setActiveTab("notifications")}
              className={`${styles.tabBtn} ${activeTab === "notifications" ? styles.tabBtnActive : ""}`}
            >
              <span>🔔</span>
              <span>Notification Alerts</span>
            </button>

            {isLawyer && (
              <Link
                href="/lawyer/profile"
                className={styles.tabBtn}
                style={{ marginTop: "12px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}
              >
                <span>⚖</span>
                <span>Bar Verification & Slots ↗</span>
              </Link>
            )}
          </nav>

          {/* Content Panel */}
          <div className={styles.contentCard}>
            {/* TAB 1: PROFILE & IDENTITY */}
            {activeTab === "profile" && (
              <div>
                <div className={styles.sectionHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>Profile & Contact Information</h2>
                    <p className={styles.sectionDescription}>
                      Official contact and location records used for matter representation and counsel discovery.
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    {profile && "verification_status" in profile && profile.verification_status && (
                      <StatusBadge
                        status={profile.verification_status === "APPROVED" ? "VERIFIED" : profile.verification_status}
                        label={`BAR: ${profile.verification_status}`}
                      />
                    )}
                    <StatusBadge status={user.account_status || "ACTIVE"} label={user.account_status} />
                  </div>
                </div>

                {profileSuccess && (
                  <div className={styles.alertSuccess}>
                    <span>✓</span> {profileSuccess}
                  </div>
                )}
                {profileError && (
                  <div className={styles.alertError}>
                    <span>⚠️</span> {profileError}
                  </div>
                )}

                <form onSubmit={handleProfileSubmit}>
                  <div className={styles.formGrid}>
                    <div className={styles.formGroup}>
                      <label className={styles.label}>Account Email (Primary ID)</label>
                      <input
                        type="email"
                        readOnly
                        value={user.email}
                        className={`${styles.input} ${styles.inputReadOnly}`}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.label}>Account Role</label>
                      <input
                        type="text"
                        readOnly
                        value={user.role}
                        className={`${styles.input} ${styles.inputReadOnly}`}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.label}>Full Name / Caption</label>
                      <input
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="e.g. Adv. Rajesh Sharma"
                        className={styles.input}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.label}>Contact Phone Number</label>
                      <input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="+91 98765 43210"
                        className={styles.input}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.label}>Location / Primary City</label>
                      <input
                        type="text"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        placeholder="e.g. New Delhi, NCR"
                        className={styles.input}
                      />
                    </div>

                    {isLawyer && (
                      <>
                        <div className={styles.formGroup}>
                          <label className={styles.label}>Consultation Fee (₹ INR)</label>
                          <input
                            type="number"
                            min={0}
                            step={100}
                            value={fee}
                            onChange={(e) => setFee(e.target.value)}
                            placeholder="2500"
                            className={styles.input}
                          />
                        </div>

                        <div className={styles.formGroup}>
                          <label className={styles.label}>Years of Experience at Bar</label>
                          <input
                            type="number"
                            min={0}
                            max={60}
                            value={experience}
                            onChange={(e) => setExperience(e.target.value)}
                            placeholder="12"
                            className={styles.input}
                          />
                        </div>

                        <div className={`${styles.formGroup} ${styles.fullWidth}`}>
                          <label className={styles.label}>Practice Areas (Comma-separated)</label>
                          <input
                            type="text"
                            value={practiceAreas}
                            onChange={(e) => setPracticeAreas(e.target.value)}
                            placeholder="Corporate Litigation, Commercial Arbitration, Intellectual Property"
                            className={styles.input}
                          />
                        </div>

                        <div className={`${styles.formGroup} ${styles.fullWidth}`}>
                          <label className={styles.label}>Courts of Practice (Comma-separated)</label>
                          <input
                            type="text"
                            value={courtJurisdictions}
                            onChange={(e) => setCourtJurisdictions(e.target.value)}
                            placeholder="Supreme Court of India, Delhi High Court, NCLT New Delhi"
                            className={styles.input}
                          />
                        </div>

                        <div className={`${styles.formGroup} ${styles.fullWidth}`}>
                          <label className={styles.label}>Professional Bio & Background</label>
                          <textarea
                            value={bio}
                            onChange={(e) => setBio(e.target.value)}
                            placeholder="Summarize your bar credentials, statutory specialization, and chamber practice..."
                            className={styles.textarea}
                          />
                        </div>
                      </>
                    )}
                  </div>

                  <div className={styles.btnRow}>
                    <button type="submit" disabled={savingProfile} className={styles.saveBtn}>
                      {savingProfile ? "Saving Changes..." : "Save Profile Details"}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* TAB 2: SECURITY & PASSWORD */}
            {activeTab === "security" && (
              <div>
                <div className={styles.sectionHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>Security & Access Protection</h2>
                    <p className={styles.sectionDescription}>
                      Update your Argon2id hashed password and review active cryptographic session parameters.
                    </p>
                  </div>
                </div>

                <div className={styles.securityCard}>
                  <div className={styles.securityHeader}>
                    <span>🛡</span>
                    <span>Ed25519 Token Authentication & Session Defense</span>
                  </div>
                  <p className={styles.securityText}>
                    Legal Case Companion employs asymmetric Ed25519 JWT signing, strict refresh-token family rotation with automatic reuse detection, and double-submit CSRF cookie mitigation.
                  </p>
                </div>

                {passwordSuccess && (
                  <div className={styles.alertSuccess}>
                    <span>✓</span> {passwordSuccess}
                  </div>
                )}
                {passwordError && (
                  <div className={styles.alertError}>
                    <span>⚠️</span> {passwordError}
                  </div>
                )}

                <form onSubmit={handlePasswordSubmit}>
                  <div className={styles.formGrid}>
                    <div className={`${styles.formGroup} ${styles.fullWidth}`}>
                      <label className={styles.label}>Current Account Password</label>
                      <input
                        type="password"
                        required
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        placeholder="Enter current password..."
                        className={styles.input}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.label}>New Secure Password (Min 8 chars)</label>
                      <input
                        type="password"
                        required
                        minLength={8}
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="Enter new password..."
                        className={styles.input}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.label}>Confirm New Password</label>
                      <input
                        type="password"
                        required
                        minLength={8}
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Confirm new password..."
                        className={styles.input}
                      />
                    </div>
                  </div>

                  <div className={styles.btnRow}>
                    <button type="submit" disabled={savingPassword} className={styles.saveBtn}>
                      {savingPassword ? "Updating Password..." : "Update Password"}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* TAB 3: NOTIFICATION PREFERENCES */}
            {activeTab === "notifications" && (
              <div>
                <div className={styles.sectionHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>Notification Delivery Preferences</h2>
                    <p className={styles.sectionDescription}>
                      Configure instant alerts for court hearings, task deadlines, and scheduled client consultations.
                    </p>
                  </div>
                  {savingPrefs && <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Saving...</span>}
                </div>

                {prefSuccess && (
                  <div className={styles.alertSuccess}>
                    <span>✓</span> {prefSuccess}
                  </div>
                )}
                {prefError && (
                  <div className={styles.alertError}>
                    <span>⚠️</span> {prefError}
                  </div>
                )}

                <div>
                  <div className={styles.prefItem}>
                    <div className={styles.prefInfo}>
                      <div className={styles.prefTitle}>Master Email Notifications</div>
                      <div className={styles.prefDesc}>
                        Receive transactional email summaries and critical operational alerts for your registered email address ({user.email}).
                      </div>
                    </div>
                    <label className={styles.toggleSwitch}>
                      <input
                        type="checkbox"
                        checked={preferences.email_enabled}
                        onChange={(e) => handlePrefToggle("email_enabled", e.target.checked)}
                      />
                      <span className={styles.toggleSlider}></span>
                    </label>
                  </div>

                  <div className={styles.prefItem}>
                    <div className={styles.prefInfo}>
                      <div className={styles.prefTitle}>Matter & Hearing Updates</div>
                      <div className={styles.prefDesc}>
                        Alerts for new case assignments, participant additions, next date of hearing (NDOH) changes, and statutory limitation deadlines.
                      </div>
                    </div>
                    <label className={styles.toggleSwitch}>
                      <input
                        type="checkbox"
                        checked={preferences.case_updates}
                        onChange={(e) => handlePrefToggle("case_updates", e.target.checked)}
                      />
                      <span className={styles.toggleSlider}></span>
                    </label>
                  </div>

                  <div className={styles.prefItem}>
                    <div className={styles.prefInfo}>
                      <div className={styles.prefTitle}>Case Tasks & Document Readiness</div>
                      <div className={styles.prefDesc}>
                        Notifications when tasks are assigned to you, due dates are approaching, or uploaded court filings complete security scans.
                      </div>
                    </div>
                    <label className={styles.toggleSwitch}>
                      <input
                        type="checkbox"
                        checked={preferences.task_updates}
                        onChange={(e) => handlePrefToggle("task_updates", e.target.checked)}
                      />
                      <span className={styles.toggleSlider}></span>
                    </label>
                  </div>

                  <div className={styles.prefItem}>
                    <div className={styles.prefInfo}>
                      <div className={styles.prefTitle}>Consultation & Payment Updates</div>
                      <div className={styles.prefDesc}>
                        Instant alerts when consultation requests are received, accepted, rescheduled, cancelled, or paid via Stripe.
                      </div>
                    </div>
                    <label className={styles.toggleSwitch}>
                      <input
                        type="checkbox"
                        checked={preferences.consultation_updates}
                        onChange={(e) => handlePrefToggle("consultation_updates", e.target.checked)}
                      />
                      <span className={styles.toggleSlider}></span>
                    </label>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
