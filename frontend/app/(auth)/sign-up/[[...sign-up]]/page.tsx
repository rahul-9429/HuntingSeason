import { SignUp } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthFormSkeleton } from "../../auth-form-skeleton";

export const metadata: Metadata = { title: "Create account" };

export default function SignUpPage() {
  return (
    <Suspense fallback={<AuthFormSkeleton />}>
      <SignUp />
    </Suspense>
  );
}
