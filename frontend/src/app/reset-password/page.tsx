"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import styles from "../login/auth.module.css";
import Link from "next/link";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const queryToken = searchParams.get("token");
    if (queryToken) {
      setToken(queryToken);
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!token.trim()) {
      setError("Password reset token is required.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await apiClient.post(
        "/api/v1/auth/password/reset/confirm",
        {
          token: token.trim(),
          new_password: password,
        },
        { requireAuth: false }
      );

      setSuccess(true);
      setTimeout(() => {
        router.push("/login");
      }, 2500);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Password reset failed. The token may be expired or already used.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.authContainer}>
      <div className={`glass-panel ${styles.authCard} animate-fade-in`}>
        <h1 className="text-gradient">Set New Password</h1>
        <p className={styles.subtitle}>
          Enter and confirm your new account password below.
        </p>

        {error && <div className={styles.errorAlert}>{error}</div>}

        {success ? (
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
              ✓ <b>Password Reset Successfully!</b>
              <p style={{ margin: "8px 0 0", fontSize: "13px" }}>
                All previous login sessions have been invalidated for security. Redirecting to login...
              </p>
            </div>

            <Link href="/login" className="btn btn-primary" style={{ display: "inline-block", width: "100%", padding: "12px" }}>
              Proceed to Login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            {!searchParams.get("token") && (
              <div className="input-group">
                <label className="input-label" htmlFor="reset-token">
                  Reset Token
                </label>
                <input
                  id="reset-token"
                  type="text"
                  className="input-field"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Paste reset token from email"
                  required
                  disabled={loading}
                />
              </div>
            )}

            <div className="input-group">
              <label className="input-label" htmlFor="new-password">
                New Password (minimum 8 characters)
              </label>
              <input
                id="new-password"
                type="password"
                className="input-field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
                disabled={loading}
              />
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="confirm-password">
                Confirm New Password
              </label>
              <input
                id="confirm-password"
                type="password"
                className="input-field"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              className={`btn btn-primary ${styles.submitBtn} ${loading ? "btn-disabled" : ""}`}
              disabled={loading || !password || !confirmPassword}
            >
              {loading ? "Resetting Password..." : "Update Password"}
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className={styles.authContainer}><div className={styles.authCard}>Loading...</div></div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
