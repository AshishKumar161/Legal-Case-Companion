"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, UserRole } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import styles from "../login/auth.module.css";

export default function Register() {
  const router = useRouter();
  const { login } = useAuth();

  // Step state: 'form' -> 'otp' -> 'success'
  const [step, setStep] = useState<"form" | "otp" | "success">("form");

  // Registration form state
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("CLIENT");

  // OTP string state (unified 6 digits)
  const [otpCode, setOtpCode] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  // UI status state
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  // Resend cooldown timer
  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendMessage, setResendMessage] = useState("");

  // Countdown timer effect
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const interval = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendCooldown]);

  // Focus input when transitioning to OTP step
  useEffect(() => {
    if (step === "otp") {
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [step]);

  // Handle Step 1: Account registration & OTP dispatch
  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setError("Password must contain at least one letter and one number.");
      return;
    }

    const emailDomain = email.split("@")[1]?.toLowerCase().trim();
    const commonTypos: Record<string, string> = {
      "gmai.com": "gmail.com",
      "gmaill.com": "gmail.com",
      "gamil.com": "gmail.com",
      "gmial.com": "gmail.com",
      "hotmial.com": "hotmail.com",
      "yaho.com": "yahoo.com",
      "outlok.com": "outlook.com",
    };
    if (emailDomain && commonTypos[emailDomain]) {
      setError(`Did you mean @${commonTypos[emailDomain]}? Please verify your email address.`);
      return;
    }

    setLoading(true);

    try {
      // Register user (backend creates user and dispatches 6-digit OTP email)
      await apiClient.post("/api/v1/auth/register", {
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password: password,
        role: role,
      });

      // Transition to OTP verification step
      setStep("otp");
      setOtpCode("");
      setResendCooldown(30);
      setResendMessage("A 6-digit verification code has been dispatched to your email.");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Registration failed. Please check your details and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle Step 2: Verify OTP and automatically log in
  const verifyOtpCode = async (code: string) => {
    const cleanCode = code.trim();
    if (cleanCode.length !== 6) {
      setError("Please enter the complete 6-digit verification code.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const res = await apiClient.post(
        "/api/v1/auth/email/verify/otp",
        {
          email: email.trim().toLowerCase(),
          otp: cleanCode,
        },
        { requireAuth: false }
      );

      if (res?.access_token) {
        // Extract user id from JWT claims
        let userId = "";
        try {
          const payload = JSON.parse(atob(res.access_token.split(".")[1]));
          userId = payload.sub || "";
        } catch {
          // fallback
        }

        // Establish active login session in AuthProvider
        login(
          res.access_token,
          {
            id: userId,
            email: email.trim().toLowerCase(),
            role: role,
            account_status: "ACTIVE",
            full_name: fullName.trim(),
          },
          res.refresh_token
        );

        setStep("success");

        // Redirect user into their lightweight tailored onboarding
        setTimeout(() => {
          router.push("/onboarding");
        }, 1200);
      } else {
        setError("Verification succeeded. Please proceed to log in.");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Invalid or expired verification code. Please check and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleManualOtpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    verifyOtpCode(otpCode);
  };

  // Handle Resending OTP
  const handleResendOtp = async () => {
    if (resendCooldown > 0 || resending) return;

    setResending(true);
    setError("");
    setResendMessage("");

    try {
      await apiClient.post(
        "/api/v1/auth/email/verify/request",
        { email: email.trim().toLowerCase() },
        { requireAuth: false }
      );
      setResendCooldown(30);
      setResendMessage("A fresh 6-digit verification code has been dispatched to your email.");
      setOtpCode("");
      inputRef.current?.focus();
    } catch {
      setResendMessage("If an account exists, a new code has been dispatched.");
    } finally {
      setResending(false);
    }
  };

  // Google SSO handler
  const handleGoogleSignup = async () => {
    setError("");
    setGoogleLoading(true);
    try {
      const callbackUrl = `${window.location.origin}/auth/callback`;
      const res = await apiClient.get(
        `/api/v1/auth/google/login?redirect_uri=${encodeURIComponent(callbackUrl)}&return_url=/dashboard`,
        { requireAuth: false }
      );
      if (res?.authorization_url) {
        window.location.href = res.authorization_url;
      } else {
        setError("Could not retrieve Google authorization URL");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.toLowerCase().includes("not configured")) {
          setError(
            "Google sign-up is currently unavailable in this environment. Please register with your email and password."
          );
        } else {
          setError(err.message);
        }
      } else {
        setError("Failed to initiate Google signup");
      }
      setGoogleLoading(false);
    }
  };

  return (
    <div className={styles.authContainer}>
      <div className={`glass-panel ${styles.authCard} animate-fade-in`}>
        {step === "form" && (
          <>
            <h1 className="text-gradient">Create Account</h1>
            <p className={styles.subtitle}>Join Legal Case Companion</p>

            {error && <div className={styles.errorAlert}>{error}</div>}

            <button
              type="button"
              onClick={handleGoogleSignup}
              disabled={googleLoading || loading}
              className={styles.googleBtn}
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              {googleLoading ? "Connecting to Google..." : "Continue with Google"}
            </button>

            <div className={styles.oauthDivider}>
              <span>or sign up with email</span>
            </div>

            <form onSubmit={handleRegisterSubmit} className={styles.form}>
              <div className={styles.roleSelect}>
                <button
                  type="button"
                  className={`${styles.roleBtn} ${role === "CLIENT" ? styles.active : ""}`}
                  onClick={() => setRole("CLIENT")}
                >
                  I am a Client
                </button>
                <button
                  type="button"
                  className={`${styles.roleBtn} ${role === "LAWYER" ? styles.active : ""}`}
                  onClick={() => setRole("LAWYER")}
                >
                  I am a Lawyer
                </button>
              </div>

              <div className="input-group">
                <label className="input-label" htmlFor="register-fullname">
                  Full Name
                </label>
                <input
                  id="register-fullname"
                  type="text"
                  className="input-field"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Adv. Priya Sharma / Rajesh Kumar"
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label" htmlFor="register-email">
                  Email Address
                </label>
                <input
                  id="register-email"
                  type="email"
                  className="input-field"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label" htmlFor="register-password">
                  Password
                </label>
                <input
                  id="register-password"
                  type="password"
                  className="input-field"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={8}
                />
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    marginTop: "4px",
                    display: "block",
                  }}
                >
                  Must be at least 8 characters with letters and numbers
                </span>
              </div>

              <button
                type="submit"
                className={`btn btn-primary ${styles.submitBtn} ${loading ? "btn-disabled" : ""}`}
                disabled={loading || googleLoading}
              >
                {loading ? "Sending verification code..." : "Sign Up"}
              </button>
            </form>

            <div className={styles.authLinks}>
              <Link href="/login">Already have an account? Log in</Link>
            </div>
          </>
        )}

        {step === "otp" && (
          <div className="animate-fade-in">
            <h1 className="text-gradient">Verify Email</h1>
            <p className={styles.subtitle} style={{ marginBottom: "16px" }}>
              Enter the 6-digit verification code sent to your inbox
            </p>

            <div className={styles.otpEmailBadge}>
              ✉️ <b>{email}</b>
            </div>

            {resendMessage && (
              <div className={styles.infoAlert} style={{ textAlign: "center" }}>
                {resendMessage}
              </div>
            )}

            {error && <div className={styles.errorAlert}>{error}</div>}

            <form onSubmit={handleManualOtpSubmit} className={styles.form}>
              <div
                className={styles.otpBoxesWrapper}
                onClick={() => inputRef.current?.focus()}
              >
                {[0, 1, 2, 3, 4, 5].map((i) => {
                  const digit = otpCode[i] || "";
                  const isFilled = Boolean(digit);
                  const isActive =
                    i === otpCode.length || (i === 5 && otpCode.length === 6);
                  return (
                    <div
                      key={i}
                      className={`${styles.otpSegment} ${
                        isFilled ? styles.filled : ""
                      } ${isActive ? styles.active : ""}`}
                    >
                      {digit}
                    </div>
                  );
                })}

                <input
                  ref={inputRef}
                  id="otp-unified-input"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => {
                    const clean = e.target.value.replace(/\D/g, "").slice(0, 6);
                    setOtpCode(clean);
                    if (clean.length === 6) {
                      verifyOtpCode(clean);
                    }
                  }}
                  className={styles.otpUnifiedInput}
                  disabled={loading}
                  autoFocus
                />
              </div>

              <button
                type="submit"
                className={`btn btn-primary ${styles.submitBtn} ${
                  loading ? "btn-disabled" : ""
                }`}
                disabled={loading || otpCode.length !== 6}
              >
                {loading ? "Verifying & Connecting..." : "Verify & Connect"}
              </button>
            </form>

            <div style={{ marginTop: "24px", textAlign: "center" }}>
              <button
                type="button"
                onClick={handleResendOtp}
                disabled={resendCooldown > 0 || resending}
                className={styles.resendBtn}
              >
                {resending
                  ? "Dispatching new code..."
                  : resendCooldown > 0
                  ? `Resend code in ${resendCooldown}s`
                  : "Didn't receive the code? Resend Code"}
              </button>
            </div>

            <div style={{ marginTop: "12px", textAlign: "center" }}>
              <button
                type="button"
                onClick={() => {
                  setError("");
                  setStep("form");
                }}
                className={styles.backBtn}
              >
                ← Wrong email? Edit registration details
              </button>
            </div>

            <div className={styles.authLinks} style={{ marginTop: "20px" }}>
              <Link href="/login">Already verified? Return to Login</Link>
            </div>
          </div>
        )}

        {step === "success" && (
          <div className="animate-fade-in" style={{ textAlign: "center", padding: "20px 0" }}>
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "50%",
                background: "rgba(16, 185, 129, 0.15)",
                border: "2px solid #10b981",
                color: "#10b981",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "2rem",
                margin: "0 auto 20px auto",
              }}
            >
              ✓
            </div>
            <h2 style={{ color: "#ffffff", fontSize: "1.5rem", marginBottom: "8px" }}>
              Email Verified Successfully!
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginBottom: "24px" }}>
              Account activated. Connecting you to your Legal Case Companion dashboard...
            </p>
            <div
              style={{
                display: "inline-block",
                padding: "8px 16px",
                borderRadius: "20px",
                background: "rgba(59, 130, 246, 0.12)",
                color: "#60a5fa",
                fontSize: "0.85rem",
              }}
            >
              Redirecting now...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
