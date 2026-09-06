"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";

export function Navbar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const [istTime, setIstTime] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setIstTime(
        now.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        }) + " IST"
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

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
        background: "rgba(7, 9, 14, 0.82)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--border-subtle)",
        height: "68px",
        display: "flex",
        alignItems: "center",
        transition: "all var(--transition-fast)",
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
        {/* Brand Logo & Name */}
        <Link
          href="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            fontSize: "19px",
            fontWeight: 700,
            fontFamily: "Outfit, sans-serif",
            color: "var(--text-primary)",
            letterSpacing: "-0.5px",
          }}
        >
          <span
            style={{
              width: "34px",
              height: "34px",
              borderRadius: "10px",
              background: "var(--accent-gradient)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
              color: "#fff",
              boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
            }}
          >
            ⚖
          </span>
          <span style={{ fontWeight: 800 }}>Legal Case Companion</span>
        </Link>

        {/* Desktop Navigation */}
        <nav
          style={{
            display: "flex",
            alignItems: "center",
            gap: "28px",
          }}
          className="desktop-nav"
        >
          <Link
            href="/lawyers"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
              transition: "color var(--transition-fast)",
            }}
          >
            Advocate Directory
          </Link>
          <Link
            href="/#features"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
              transition: "color var(--transition-fast)",
            }}
          >
            Platform Capabilities
          </Link>
          <Link
            href="/#security"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
              transition: "color var(--transition-fast)",
            }}
          >
            Security & DPDP
          </Link>

          {/* Live Indian Standard Time Clock Indicator */}
          {istTime && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "4px 10px",
                borderRadius: "var(--radius-full)",
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid var(--border-subtle)",
                fontSize: "11px",
                fontFamily: "'JetBrains Mono', monospace",
                color: "var(--text-secondary)",
              }}
            >
              <span className="pulse-dot" style={{ background: "#10b981" }} />
              <span>{istTime}</span>
            </div>
          )}
        </nav>

        {/* Public Auth Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
          <Link
            href="/login"
            style={{
              fontSize: "13px",
              color: "var(--text-primary)",
              padding: "6px 14px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-subtle)",
              background: "rgba(255, 255, 255, 0.03)",
              fontWeight: 600,
              transition: "all var(--transition-fast)",
              whiteSpace: "nowrap",
            }}
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="btn btn-primary nav-desktop-only"
            style={{ padding: "6px 16px", fontSize: "13px", whiteSpace: "nowrap" }}
          >
            Launch Workspace →
          </Link>
        </div>
      </div>
    </header>
  );
}
