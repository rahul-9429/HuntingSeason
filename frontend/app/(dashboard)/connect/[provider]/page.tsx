"use client";

import { LoaderCircle, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { mailProviderLabel } from "@/lib/labels";
import { isMailProvider, useFinishMailboxConnect } from "@/lib/queries/mailbox";

export default function ConnectMailboxPage({ params }: { params: Promise<{ provider: string }> }) {
  const { provider } = use(params);
  const finish = useFinishMailboxConnect();
  const router = useRouter();
  const toast = useToast();
  const started = useRef(false);

  useEffect(() => {
    if (started.current || !isMailProvider(provider)) return;
    started.current = true;
    finish.mutate(
      { provider, url: window.location.href },
      {
        onSuccess: (mailbox) => {
          toast({ title: `${mailProviderLabel[provider]} connected`, description: mailbox.email });
          router.replace("/profile?tab=integrations");
        },
      },
    );
  }, [provider, finish, router, toast]);

  const name = isMailProvider(provider) ? mailProviderLabel[provider] : "your mailbox";
  const failed = !isMailProvider(provider) || finish.isError;

  return (
    <div className="scrollbar-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-[520px] px-5 py-16 sm:px-8">
        <section className="rounded-xl border-2 border-line-strong bg-surface p-6">
          {failed ? (
            <>
              <p className="flex items-center gap-2 text-ui font-semibold text-ink">
                <TriangleAlert className="size-4 text-amber-600" />
                Couldn&apos;t connect {name}
              </p>
              <p className="mt-1.5 text-ui text-ink-2">
                {isMailProvider(provider) ? errorMessage(finish.error) : "That isn't a mail provider we support."}
              </p>
              <Button asChild size="sm" variant="secondary" className="mt-4">
                <Link href="/profile?tab=integrations">Back to integrations</Link>
              </Button>
            </>
          ) : (
            <>
              <p className="flex items-center gap-2 text-ui font-semibold text-ink">
                <LoaderCircle className="size-4 animate-spin text-accent-700" />
                Connecting {name}…
              </p>
              <p className="mt-1.5 text-ui text-ink-2">This takes a few seconds.</p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
