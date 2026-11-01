import { clerkMiddleware } from "@clerk/nextjs/server";
import { SIGN_IN_URL, SIGN_UP_URL, isPublicPath } from "@/lib/auth";

export default clerkMiddleware(
  async (auth, request) => {
    if (isPublicPath(request.nextUrl.pathname)) return;
    const { userId, redirectToSignIn } = await auth();
    if (!userId) return redirectToSignIn();
  },
  { signInUrl: SIGN_IN_URL, signUpUrl: SIGN_UP_URL },
);

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
