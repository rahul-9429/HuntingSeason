import { SignIn } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthFormSkeleton } from "../../auth-form-skeleton";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <Suspense fallback={<AuthFormSkeleton />}>
      <SignIn />
    </Suspense>
  );
}
