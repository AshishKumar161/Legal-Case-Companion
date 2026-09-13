import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/providers/AuthProvider";
import { Navbar } from "@/components/Navbar";
import { AppShell } from "@/components/AppShell/AppShell";

export const metadata: Metadata = {
  title: "Legal Case Companion | Secure Legal Tech Platform",
  description:
    "A production-grade legal technology platform connecting clients and verified lawyers in India.",
  icons: {
    icon: "/logo-icon.png",
    shortcut: "/logo-icon.png",
    apple: "/logo-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body data-gramm="false" data-gramm_editor="false" data-enable-grammarly="false">
        <AuthProvider>
          <Navbar />
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
