"use client";

import { useEffect, useState, Suspense, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiClient } from "@/api/client";
import { useAuth, UserRole } from "@/providers/AuthProvider";
import Link from "next/link";
import styles from "../../login/auth.module.css";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const requestSentRef = useRef(false);

  useEffect(() => {
    const processCallback = async () => {
      const error = searchParams.get("error");
      const errorDescription = searchParams.get("error_description");
      const code = searchParams.get("code");
      const state = searchParams.get("state");

      if (error) {
        setStatus("error");
        if (error === "access_denied") {
          setErrorMessage("Google sign-in was cancelled by the user.");
        } else if (errorDescription) {
          setErrorMessage(`Google authorization failed: ${error} (${errorDescription})`);
        } else {
          setErrorMessage(`Google authorization failed: ${error}`);
        }
        return;
      }

      if (!code || !state) {
        setStatus("error");
        setErrorMessage("Missing required authorization code or state parameter.");
        return;
      }

      if (requestSentRef.current) return;
      requestSentRef.current = true;

      try {
        const redirectUri = `${window.location.origin}/auth/callback`;
        const res = await apiClient.post(
          "/api/v1/auth/google/callback",
          {
            code,
            state,
            redirect_uri: redirectUri,
          },
          { requireAuth: false }
        );

        if (res?.access_token) {
          let userId = "";
          let userRole: UserRole | null = null;
          let email = "";

          try {
            const payload = JSON.parse(atob(res.access_token.split(".")[1]));
            if (payload.sub) userId = payload.sub;
            if (
              payload.role &&
              (payload.role === "CLIENT" || payload.role === "LAWYER" || payload.role === "ADMIN")
            ) {
              userRole = payload.role as UserRole;
            }
            if (payload.email) email = payload.email;
          } catch (e) {
            console.warn("Could not parse JWT token payload:", e);
          }

          if (!userRole || !userId) {
            setStatus("error");
            setErrorMessage("Identity verification succeeded, but credentials lack authoritative role information.");
            return;
          }

          // Authorize session strictly in current tab
          login(
            res.access_token,
            {
              id: userId,
              email,
              role: userRole,
              account_status: "ACTIVE",
            },
            res.refresh_token
          );

          setStatus("success");

          // Validate internal redirect destination against open redirect
          const safeReturnUrl =
            res.return_url &&
            res.return_url.startsWith("/") &&
            !res.return_url.startsWith("//") &&
            !res.return_url.includes("://")
              ? res.return_url
              : null;

          if (safeReturnUrl && safeReturnUrl !== "/dashboard") {
            router.push(safeReturnUrl);
          } else if (userRole === "ADMIN") {
            router.push("/admin/dashboard");
          } else if (userRole === "LAWYER") {
            router.push("/lawyer/dashboard");
          } else {
            router.push("/dashboard");
          }
        } else {
          setStatus("error");
          setErrorMessage("Failed to obtain session tokens from server.");
        }
      } catch (err: unknown) {
        setStatus("error");
        if (err instanceof Error) {
          setErrorMessage(err.message);
        } else {
          setErrorMessage("Authentication failed during Google identity verification.");
        }
      }
    };

    void processCallback();
  }, [searchParams, router, login]);

  return (
    <div className={styles.authContainer}>
      <div className={`glass-panel ${styles.authCard} animate-fade-in`}>
        {status === "loading" && (
          <>
            <h1 className="text-gradient">Verifying Identity</h1>
            <p className={styles.subtitle}>Securing your session with Google OpenID Connect...</p>
            <div style={{ marginTop: "24px", color: "var(--accent-primary)" }}>
              Please wait while we verify your credentials...
            </div>
          </>
        )}

        {status === "success" && (
          <>
            <h1 className="text-gradient">Authenticated</h1>
            <p className={styles.subtitle}>Redirecting to your dashboard...</p>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="text-gradient">Authentication Error</h1>
            <p className={styles.subtitle}>Could not complete Google Sign-In</p>
            <div className={styles.errorAlert}>{errorMessage}</div>
            <div className={styles.authLinks}>
              <Link href="/login" className="btn btn-primary" style={{ display: "inline-block", padding: "10px 20px" }}>
                Return to Login
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div className={styles.authContainer}><div className={styles.authCard}>Loading...</div></div>}>
      <AuthCallbackContent />
    </Suspense>
  );
}
