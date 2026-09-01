"use client";

import { useState } from "react";
import { apiClient } from "@/api/client";
import styles from "../login/auth.module.css";
import Link from "next/link";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await apiClient.post(
        "/api/v1/auth/password/reset/request",
        {
          email: email.trim().toLowerCase(),
        },
        { requireAuth: false }
      );
      setSubmitted(true);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to request password reset. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.authContainer}>
      <div className={`glass-panel ${styles.authCard} animate-fade-in`}>
        <h1 className="text-gradient">Reset Password</h1>
        <p className={styles.subtitle}>
          Enter your registered email address and we will dispatch a recovery link.
        </p>

        {error && <div className={styles.errorAlert}>{error}</div>}

        {submitted ? (
          <div style={{ textAlign: "left", margin: "20px 0" }}>
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
              <b>Check your inbox:</b> If an account exists with{" "}
              <b>{email.trim().toLowerCase()}</b>, a password reset link has been dispatched.
              The link will expire in 15 minutes.
            </div>

            <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              Did not receive an email? Check your spam folder or ensure you entered the exact email
              address used during registration.
            </p>

            <div style={{ marginTop: "24px", textAlign: "center" }}>
              <Link href="/login" className="btn btn-primary" style={{ display: "inline-block", width: "100%", padding: "12px" }}>
                Return to Login
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className="input-group">
              <label className="input-label" htmlFor="recovery-email">
                Registered Email Address
              </label>
              <input
                id="recovery-email"
                type="email"
                className="input-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="advocate@example.com"
                required
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              className={`btn btn-primary ${styles.submitBtn} ${loading ? "btn-disabled" : ""}`}
              disabled={loading || !email.trim()}
            >
              {loading ? "Dispatching Link..." : "Send Password Reset Link"}
            </button>
          </form>
        )}

        <div className={styles.authLinks} style={{ marginTop: "24px" }}>
          <Link href="/login">Remembered your password? Log in</Link>
        </div>
      </div>
    </div>
  );
}
