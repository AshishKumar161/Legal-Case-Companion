"use client";

import { useState, useEffect, Suspense } from 'react';
import { useAuth, UserRole } from '@/providers/AuthProvider';
import { apiClient } from '@/api/client';
import styles from './auth.module.css';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { UserIcon, ScalesIcon, ShieldIcon } from '@/components/ui/Icons';

function getSafeRedirectUrl(url: string | null): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  // Must be an internal relative path, preventing open redirects
  if (trimmed.startsWith('/') && !trimmed.startsWith('//') && !trimmed.includes('://')) {
    return trimmed;
  }
  return null;
}

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [demoLoadingRole, setDemoLoadingRole] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get('expired') === '1') {
      setInfo('Your session has expired. Please log in again to continue.');
    }

    // Safe pre-fill for email input only (no plaintext password handling)
    const initialEmail = searchParams.get('email');
    if (initialEmail) {
      setEmail(initialEmail.trim());
    }
  }, [searchParams]);

  const executeLogin = async (targetEmail: string, targetPassword: string) => {
    setError('');
    setInfo('');

    try {
      const res = await apiClient.post('/api/v1/auth/login', {
        email: targetEmail.trim(),
        password: targetPassword,
      });

      let userId = "";
      let userRole: UserRole | null = null;

      try {
        const base64Url = res.access_token.split('.')[1] || '';
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const padLen = (4 - (base64.length % 4)) % 4;
        const paddedBase64 = base64 + '='.repeat(padLen);
        const payload = JSON.parse(atob(paddedBase64));
        if (payload.sub) userId = payload.sub;
        if (
          payload.role &&
          (payload.role === 'CLIENT' || payload.role === 'LAWYER' || payload.role === 'ADMIN')
        ) {
          userRole = payload.role as UserRole;
        }
      } catch (decodeErr) {
        console.warn("Could not decode JWT payload directly:", decodeErr);
      }

      if (!userRole || !userId) {
        throw new Error("Login failed: Authentication token contains missing or invalid role credentials.");
      }

      // Establish isolated session strictly in current tab
      login(
        res.access_token,
        {
          id: userId,
          email: targetEmail.trim().toLowerCase(),
          role: userRole,
          account_status: "ACTIVE",
        },
        res.refresh_token
      );

      const safeRedirect = getSafeRedirectUrl(searchParams.get('redirect'));
      if (safeRedirect) {
        router.push(safeRedirect);
      } else if (userRole === 'ADMIN') {
        router.push("/admin/dashboard");
      } else if (userRole === 'LAWYER') {
        router.push("/lawyer/dashboard");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Login failed');
      }
      throw err;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await executeLogin(email, password);
    } catch {
      // Error is set in executeLogin
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (demoEmail: string, roleName: string) => {
    setEmail(demoEmail);
    setPassword('Password123!');
    setDemoLoadingRole(roleName);
    try {
      await executeLogin(demoEmail, 'Password123!');
    } catch {
      // Error handled in executeLogin
    } finally {
      setDemoLoadingRole(null);
    }
  };

  const handleGoogleLogin = async () => {
    setError('');
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
        setError('Could not retrieve Google authorization URL');
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.toLowerCase().includes('not configured')) {
          setError('Google sign-in is currently unavailable in this environment. Please sign in with your email and password.');
        } else {
          setError(err.message);
        }
      } else {
        setError('Failed to initiate Google login');
      }
      setGoogleLoading(false);
    }
  };

  return (
    <div className={styles.authContainer}>
      <div className={`${styles.authCard} animate-fade-in`}>
        {/* Brand Emblem */}
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
        <h1 className={styles.title}>Welcome Back</h1>
        <p className={styles.subtitle}>Sign in to access your Legal Case Companion workspace</p>

        {info && <div className={styles.infoAlert}>{info}</div>}
        {error && <div className={styles.errorAlert}>{error}</div>}

        {/* 1-Click Demo Persona Access Panel */}
        <div className={styles.demoSection} suppressHydrationWarning>
          <div className={styles.demoHeader} suppressHydrationWarning>
            <span className={styles.demoBadge}>Quick Demo Access</span>
            <span className={styles.demoSubtext}>Instant sandbox evaluation</span>
          </div>
          <div className={styles.demoGrid} suppressHydrationWarning>
            <button
              type="button"
              id="demo-client-btn"
              onClick={() => handleDemoLogin('client@lcc.test', 'client')}
              disabled={loading || !!demoLoadingRole || googleLoading}
              className={`${styles.demoBtn} ${styles.demoClient}`}
              suppressHydrationWarning
            >
              <div className={styles.demoBtnContent}>
                <div className={styles.demoRoleIcon}>
                  <UserIcon size={18} color="#2563eb" />
                </div>
                <div className={styles.demoRoleInfo}>
                  <div className={styles.demoRoleTitle}>
                    <span>Vikram Sharma</span>
                    <span className={styles.demoTagClient}>Client</span>
                  </div>
                  <div className={styles.demoRoleDesc}>Citizen Dashboard & Matters</div>
                </div>
              </div>
              <div className={styles.demoAction}>
                {demoLoadingRole === 'client' ? 'Signing in...' : 'Sign In →'}
              </div>
            </button>

            <button
              type="button"
              id="demo-lawyer-btn"
              onClick={() => handleDemoLogin('advocate@lcc.test', 'lawyer')}
              disabled={loading || !!demoLoadingRole || googleLoading}
              className={`${styles.demoBtn} ${styles.demoLawyer}`}
              suppressHydrationWarning
            >
              <div className={styles.demoBtnContent}>
                <div className={styles.demoRoleIcon}>
                  <ScalesIcon size={18} color="#059669" />
                </div>
                <div className={styles.demoRoleInfo}>
                  <div className={styles.demoRoleTitle}>
                    <span>Adv. Ananya Roy</span>
                    <span className={styles.demoTagLawyer}>Advocate</span>
                  </div>
                  <div className={styles.demoRoleDesc}>Bar Council Counsel Chambers</div>
                </div>
              </div>
              <div className={styles.demoAction}>
                {demoLoadingRole === 'lawyer' ? 'Signing in...' : 'Sign In →'}
              </div>
            </button>

            <button
              type="button"
              id="demo-admin-btn"
              onClick={() => handleDemoLogin('admin@lcc.test', 'admin')}
              disabled={loading || !!demoLoadingRole || googleLoading}
              className={`${styles.demoBtn} ${styles.demoAdmin}`}
              suppressHydrationWarning
            >
              <div className={styles.demoBtnContent}>
                <div className={styles.demoRoleIcon}>
                  <ShieldIcon size={18} color="#7c3aed" />
                </div>
                <div className={styles.demoRoleInfo}>
                  <div className={styles.demoRoleTitle}>
                    <span>Platform Admin</span>
                    <span className={styles.demoTagAdmin}>Admin</span>
                  </div>
                  <div className={styles.demoRoleDesc}>Control Plane & Oversight</div>
                </div>
              </div>
              <div className={styles.demoAction}>
                {demoLoadingRole === 'admin' ? 'Signing in...' : 'Sign In →'}
              </div>
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={handleGoogleLogin}
          disabled={googleLoading || loading || !!demoLoadingRole}
          className={styles.googleBtn}
          suppressHydrationWarning
        >
          <svg width="18" height="18" viewBox="0 0 24 24" suppressHydrationWarning>
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
          {googleLoading ? 'Connecting to Google...' : 'Continue with Google'}
        </button>

        <div className={styles.oauthDivider}>
          <span>or log in with email</span>
        </div>

        <form onSubmit={handleSubmit} className={styles.form} suppressHydrationWarning>
          <div className={styles.inputGroup} suppressHydrationWarning>
            <label className={styles.inputLabel} htmlFor="email-input">Email Address</label>
            <input
              id="email-input"
              type="email"
              className={styles.inputField}
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="name@example.com"
              required
              suppressHydrationWarning
            />
          </div>

          <div className={styles.inputGroup} suppressHydrationWarning>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <label className={styles.inputLabel} htmlFor="password-input" style={{ margin: 0 }}>Password</label>
              <Link href="/forgot-password" style={{ fontSize: "12px", color: "#2563eb", fontWeight: 600, textDecoration: "none" }}>
                Forgot password?
              </Link>
            </div>
            <input
              id="password-input"
              type="password"
              className={styles.inputField}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              suppressHydrationWarning
            />
          </div>

          <button
            type="submit"
            className={styles.submitBtn}
            disabled={loading || googleLoading}
            suppressHydrationWarning
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <div className={styles.authLinks}>
          <div>
            Don&apos;t have an account? <Link href="/register">Create an account</Link>
          </div>
          <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px" }}>
            🔒 Protected by 256-bit SSL encryption • Bar Council Compliant
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Login() {
  return (
    <Suspense fallback={<div className={styles.authContainer}><div className={styles.authCard}>Loading...</div></div>}>
      <LoginForm />
    </Suspense>
  );
}
