import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/providers/ThemeProvider";
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
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('lcc_theme');
                  var theme = stored || 'light';
                  if (theme === 'system') {
                    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                  }
                  document.documentElement.setAttribute('data-theme', theme);
                } catch(e) {}

                if (typeof window !== 'undefined') {
                  const origError = console.error;
                  console.error = function(...args) {
                    const msg = typeof args[0] === 'string' ? args[0] : '';
                    if (msg.includes('bis_skin_checked') || msg.includes('browser extension') || msg.includes('did not match')) {
                      return;
                    }
                    origError.apply(console, args);
                  };
                }
              })();
            `,
          }}
        />
      </head>
      <body data-gramm="false" data-gramm_editor="false" data-enable-grammarly="false" suppressHydrationWarning>
        <ThemeProvider>
          <AuthProvider>
            <Navbar />
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

