"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";

export function Navbar() {
  const { user } = useAuth();
  const pathname = usePathname();

  // If user is authenticated or on auth forms, Navbar is not rendered.
  // The authenticated experience is managed via AppShell (Sidebar + TopBar).
  if (user || pathname === "/login" || pathname === "/register" || pathname?.startsWith("/auth/callback")) {
    return null;
  }

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 900,
        background: "rgba(8, 9, 12, 0.85)",
        backdropFilter: "blur(16px)",
        borderBottom: "1px solid var(--border-subtle)",
        height: "64px",
        display: "flex",
        alignItems: "center",
      }}
    >
      <div
        className="container"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          width: "100%",
        }}
      >
        {/* Brand */}
        <Link
          href="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "18px",
            fontWeight: 700,
            fontFamily: "Outfit, sans-serif",
            color: "var(--text-primary)",
            letterSpacing: "-0.5px",
          }}
        >
          <span
            style={{
              width: "30px",
              height: "30px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "14px",
              color: "#fff",
            }}
          >
            ⚖
          </span>
          <span>Legal Case Companion</span>
        </Link>

        {/* Public Navigation */}
        <nav style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          <Link
            href="/lawyers"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
            }}
          >
            Counsel Directory
          </Link>
          <Link
            href="/#features"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
            }}
          >
            Capabilities
          </Link>
          <Link
            href="/#security"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
            }}
          >
            Security & Architecture
          </Link>
        </nav>

        {/* Public Auth Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Link
            href="/login"
            style={{
              fontSize: "14px",
              color: "var(--text-primary)",
              padding: "7px 16px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-subtle)",
              fontWeight: 500,
            }}
          >
            Log In
          </Link>
          <Link
            href="/register"
            className="btn btn-primary"
            style={{ padding: "7px 18px", fontSize: "14px" }}
          >
            Open Legal Account
          </Link>
        </div>
      </div>
    </header>
  );
}
