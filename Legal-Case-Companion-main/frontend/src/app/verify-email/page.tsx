"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import styles from "../login/auth.module.css";
import Link from "next/link";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [autoTriggered, setAutoTriggered] = useState(false);

  useEffect(() => {
    const queryToken = searchParams.get("token");
    const queryEmail = searchParams.get("email");
    if (queryEmail) {
      setEmail(queryEmail);
    }
    if (queryToken && !autoTriggered) {
      setToken(queryToken);
      setAutoTriggered(true);
      verifyToken(queryToken, queryEmail || "");
    }
  }, [searchParams, autoTriggered]);

  const verifyToken = async (tokenToVerify: string, emailToVerify: string) => {
    if (!tokenToVerify.trim()) {
      setError("Please provide a valid verification token.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (emailToVerify && /^\d{6}$/.test(tokenToVerify.trim())) {
        const res = await apiClient.post(
          "/api/v1/auth/email/verify/otp",
          {
            email: emailToVerify.trim().toLowerCase(),
            otp: tokenToVerify.trim(),
          },
          { requireAuth: false }
        );
        if (res?.access_token) {
          let userId = "";
          try {
            const payload = JSON.parse(atob(res.access_token.split(".")[1]));
            userId = payload.sub || "";
          } catch {
            // ignore
          }
          login(res.access_token, {
            id: userId,
            email: emailToVerify.trim().toLowerCase(),
            role: "CLIENT",
            account_status: "ACTIVE",
          });
        }
      } else {
        await apiClient.post(
          "/api/v1/auth/email/verify/confirm",
          { token: tokenToVerify.trim() },
          { requireAuth: false }
        );
      }
      setSuccess(true);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Email verification failed. The link or code may have expired or already been used.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    verifyToken(token, email);
  };

  return (
    <div className={styles.authContainer}>
      <div className={`glass-panel ${styles.authCard} animate-fade-in`}>
        <h1 className="text-gradient">Verify Email</h1>
        <p className={styles.subtitle}>
          Confirm your email address to complete your account setup.
        </p>

        {error && <div className={styles.errorAlert}>{error}</div>}

        {loading ? (
          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <div style={{ fontSize: "1.2rem", marginBottom: "12px", color: "var(--text-primary)" }}>
              Verifying your email...
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
              Please wait while we validate your verification code.
            </p>
          </div>
        ) : success ? (
          <div style={{ textAlign: "center", margin: "20px 0" }}>
            <div
              style={{
                padding: "16px",
                borderRadius: "8px",
                background: "rgba(16, 185, 129, 0.12)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                color: "#10b981",
                fontSize: "14px",
                lineHeight: 1.5,
                marginBottom: "20px",
              }}
            >
              ✓ <b>Email Verified Successfully!</b>
              <p style={{ margin: "8px 0 0", fontSize: "13px" }}>
                Your email has been confirmed and your account is active.
              </p>
            </div>

            <Link
              href="/dashboard"
              className="btn btn-primary"
              style={{ display: "inline-block", width: "100%", padding: "12px", marginBottom: "12px" }}
            >
              Go to Dashboard
            </Link>

            <Link
              href="/login"
              style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}
            >
              Or proceed to Login screen
            </Link>
          </div>
        ) : (
          <form onSubmit={handleManualSubmit} className={styles.form}>
            <div className="input-group">
              <label className="input-label" htmlFor="verify-email">
                Email Address
              </label>
              <input
                id="verify-email"
                type="email"
                className="input-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                required
              />
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="verify-token">
                6-Digit Verification Code
              </label>
              <input
                id="verify-token"
                type="text"
                className="input-field"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="e.g. 849201"
                maxLength={6}
                required
                style={{ letterSpacing: "4px", fontSize: "1.2rem", textAlign: "center" }}
              />
            </div>

            <button
              type="submit"
              className={`btn btn-primary ${styles.submitBtn}`}
              disabled={loading || !token.trim()}
            >
              Verify Email & Connect
            </button>
          </form>
        )}

        <div className={styles.authLinks} style={{ marginTop: "24px" }}>
          <Link href="/login">Return to Login</Link>
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className={styles.authContainer}>
          <div className={styles.authCard}>Loading...</div>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
