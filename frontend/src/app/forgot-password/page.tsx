"use client";

import { useState } from "react";
import { apiClient } from "@/api/client";
import styles from "../login/auth.module.css";
import Link from "next/link";
import Image from "next/image";

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
      <div className={`${styles.authCard} animate-fade-in`}>
        <div className={styles.logoBadge}>
          <Image
            src="/logo-icon-white.png"
            alt="Legal Case Companion"
            width={38}
            height={38}
            style={{ objectFit: "contain", width: "38px", height: "38px" }}
            priority
          />
        </div>
        <h1 className={styles.title}>Reset Password</h1>
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
                background: "#ecfdf5",
                border: "1px solid #a7f3d0",
                color: "#065f46",
                fontSize: "14px",
                lineHeight: 1.5,
                marginBottom: "20px",
              }}
            >
              <b>Check your inbox:</b> If an account exists with{" "}
              <b>{email.trim().toLowerCase()}</b>, a password reset link has been dispatched.
              The link will expire in 15 minutes.
            </div>

            <p style={{ fontSize: "13px", color: "#64748b", lineHeight: 1.5 }}>
              Did not receive an email? Check your spam folder or ensure you entered the exact email
              address used during registration.
            </p>

            <div style={{ marginTop: "24px", textAlign: "center" }}>
              <Link href="/login" className={styles.submitBtn} style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}>
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
