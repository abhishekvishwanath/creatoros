import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Creator Intelligence OS",
  description: "The AI content strategist that knows your creator business.",
};

// Runs before hydration so the correct theme applies on first paint — no
// flash of the wrong theme, and no server/client class mismatch (the server
// always renders without .dark; this script decides synchronously on the
// client, before anything is painted).
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("theme");if(t==="dark"||(t!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches)){document.documentElement.classList.add("dark")}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
