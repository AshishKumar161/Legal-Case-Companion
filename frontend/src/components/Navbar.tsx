"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import Image from "next/image";

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
          hour12: true,
        }) + " IST"
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 30000);
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
        background: "#FFFFFF",
        borderBottom: "1px solid var(--border-subtle)",
        height: "64px",
        display: "flex",
        alignItems: "center",
        boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
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
            gap: "10px",
            fontSize: "18px",
            fontWeight: 800,
            fontFamily: "var(--font-display)",
            color: "var(--navy-primary)",
            letterSpacing: "-0.02em",
          }}
        >
          <span
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "8px",
              background: "var(--navy-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 6px rgba(15, 30, 54, 0.15)",
              overflow: "hidden",
              padding: "4px",
            }}
          >
            <Image
              src="/logo-icon-white.png"
              alt="LCC Logo"
              width={24}
              height={24}
              style={{ objectFit: "contain", width: "auto", height: "auto" }}
              priority
            />
          </span>
          <span>Legal Case Companion</span>
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
            Find a Lawyer
          </Link>
          <Link
            href="/#how-it-works"
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: "var(--text-secondary)",
              transition: "color var(--transition-fast)",
            }}
          >
            How It Works
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
            Privacy & Security
          </Link>

          {/* Live Indian Standard Time Clock Indicator */}
          {istTime && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "3px 10px",
                borderRadius: "var(--radius-full)",
                background: "var(--surface-subtle)",
                border: "1px solid var(--border-subtle)",
                fontSize: "12px",
                color: "var(--text-secondary)",
                fontWeight: 500,
              }}
            >
              <span className="pulse-dot" />
              <span>Court Hours ({istTime})</span>
            </div>
          )}
        </nav>

        {/* Public Auth Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
          <Link
            href="/login"
            style={{
              fontSize: "13px",
              color: "var(--text-primary)",
              padding: "7px 16px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
              background: "#FFFFFF",
              fontWeight: 600,
              transition: "all var(--transition-fast)",
              whiteSpace: "nowrap",
            }}
          >
            Sign In
          </Link>
          <Link
            href="/cases/new"
            className="btn btn-primary nav-desktop-only"
            style={{ padding: "7px 18px", fontSize: "13px", whiteSpace: "nowrap" }}
          >
            Start a Case →
          </Link>
        </div>
      </div>
    </header>
  );
}
