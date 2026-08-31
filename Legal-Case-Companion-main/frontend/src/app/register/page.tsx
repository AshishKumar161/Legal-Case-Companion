"use client";

import { useState } from 'react';
import { useAuth, UserRole } from '@/providers/AuthProvider';
import { apiClient } from '@/api/client';
import styles from '../login/auth.module.css';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function Register() {
  const { login } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('CLIENT');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // 1. Register user with full_name
      await apiClient.post('/api/v1/auth/register', {
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password: password,
        role: role,
      });

      // 2. Automatically login after registration
      const res = await apiClient.post('/api/v1/auth/login', {
        email: email.trim().toLowerCase(),
        password: password,
      });

      let userId = "temp";
      let userRole = role;
      try {
        const payload = JSON.parse(atob(res.access_token.split('.')[1]));
        if (payload.sub) userId = payload.sub;
        if (payload.role) userRole = payload.role;
      } catch {}

      login(res.access_token, {
        id: userId,
        email: email.trim().toLowerCase(),
        role: userRole,
        account_status: "ACTIVE",
        full_name: fullName.trim(),
      });

      if (userRole === 'LAWYER') {
        router.push("/lawyer/dashboard");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Registration failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignup = async () => {
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
        setError(err.message);
      } else {
        setError('Failed to initiate Google signup');
      }
      setGoogleLoading(false);
    }
  };

  return (
    <div className={styles.authContainer}>
      <div className={`glass-panel ${styles.authCard} animate-fade-in`}>
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
          {googleLoading ? 'Connecting to Google...' : 'Continue with Google'}
        </button>

        <div className={styles.oauthDivider}>
          <span>or sign up with email</span>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.roleSelect}>
            <button
              type="button"
              className={`${styles.roleBtn} ${role === 'CLIENT' ? styles.active : ''}`}
              onClick={() => setRole('CLIENT')}
            >
              I am a Client
            </button>
            <button
              type="button"
              className={`${styles.roleBtn} ${role === 'LAWYER' ? styles.active : ''}`}
              onClick={() => setRole('LAWYER')}
            >
              I am a Lawyer
            </button>
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="register-fullname">Full Name</label>
            <input
              id="register-fullname"
              type="text"
              className="input-field"
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              placeholder="e.g. Adv. Priya Sharma / Rajesh Kumar"
              required
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="register-email">Email Address</label>
            <input
              id="register-email"
              type="email"
              className="input-field"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="user@example.com"
              required
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="register-password">Password</label>
            <input
              id="register-password"
              type="password"
              className="input-field"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            className={`btn btn-primary ${styles.submitBtn} ${loading ? 'btn-disabled' : ''}`}
            disabled={loading || googleLoading}
          >
            {loading ? 'Creating account...' : 'Sign Up'}
          </button>
        </form>

        <div className={styles.authLinks}>
          <Link href="/login">Already have an account? Log in</Link>
        </div>
      </div>
    </div>
  );
}

