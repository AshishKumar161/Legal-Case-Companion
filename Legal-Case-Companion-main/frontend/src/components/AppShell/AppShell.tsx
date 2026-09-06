"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MobileBottomNav } from "./MobileBottomNav";
import styles from "./AppShell.module.css";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // If public route or unauthenticated, render children directly without the shell
  const isPublicRoute =
    pathname === "/" ||
    pathname === "/login" ||
    pathname === "/register" ||
    pathname?.startsWith("/auth/callback");

  if (isPublicRoute || !user) {
    return <>{children}</>;
  }

  return (
    <div className={styles.appShellContainer}>
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((prev) => !prev)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className={styles.mainWrapper}>
        <TopBar onOpenMobile={() => setMobileOpen(true)} />
        <main className={styles.contentCanvas}>{children}</main>
        <MobileBottomNav />
      </div>
    </div>
  );
}
