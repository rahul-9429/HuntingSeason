import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { AFTER_AUTH_URL, ONBOARDING_URL, SIGN_IN_URL, SIGN_UP_URL, clerkAppearance } from "@/lib/auth";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: {
    default: "Hunting Season",
    template: "%s · Hunting Season",
  },
  description: "Find the people who can get you hired — and reach them.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} h-full`}
      suppressHydrationWarning
    >
      <body className="h-full">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <ClerkProvider
            signInUrl={SIGN_IN_URL}
            signUpUrl={SIGN_UP_URL}
            signInFallbackRedirectUrl={AFTER_AUTH_URL}
            // Force, not fallback: sign-up links carry a redirect_url (from the proxy's
            // sign-in redirect) that would otherwise skip onboarding
            signUpForceRedirectUrl={ONBOARDING_URL}
            appearance={clerkAppearance}
          >
            {children}
          </ClerkProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
