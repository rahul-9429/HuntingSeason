export const SIGN_IN_URL = "/sign-in";
export const SIGN_UP_URL = "/sign-up";
export const AFTER_AUTH_URL = "/contacts";
export const ONBOARDING_URL = "/onboarding";

export function isPublicPath(pathname: string) {
  return [SIGN_IN_URL, SIGN_UP_URL].some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export const clerkAppearance = {
  variables: {
    colorPrimary: "var(--color-ink)",
    colorPrimaryForeground: "var(--color-on-ink)",
    colorForeground: "var(--color-ink)",
    colorMutedForeground: "var(--color-ink-2)",
    colorNeutral: "var(--color-ink)",
    colorBackground: "var(--color-surface)",
    colorInput: "var(--color-surface)",
    colorInputForeground: "var(--color-ink)",
    colorBorder: "var(--color-line-strong)",
    colorRing: "var(--color-accent-500)",
    colorSuccess: "#047857",
    colorDanger: "#be123c",
    borderRadius: "0.5rem",
    fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
    fontFamilyButtons: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
    fontSize: "0.8125rem",
  },
};
