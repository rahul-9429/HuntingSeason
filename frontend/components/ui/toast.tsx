"use client";

import { CircleCheck } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState } from "react";

interface ToastInput {
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

interface ToastItem extends ToastInput {
  id: number;
}

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

const DURATION_MS = 4200;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (input: ToastInput) => {
      const id = ++nextId.current;
      setToasts((current) => [...current.slice(-2), { ...input, id }]);
      window.setTimeout(() => dismiss(id), DURATION_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-5 z-[60] flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="pointer-events-auto flex max-w-md items-center gap-3 rounded-lg bg-ink py-2 pl-3 pr-2 text-ui text-on-ink shadow-pop animate-enter"
          >
            <CircleCheck className="size-4 shrink-0 text-accent-300" />
            <div className="min-w-0 py-0.5">
              <p className="font-medium">{t.title}</p>
              {t.description && <p className="text-micro text-on-ink/60">{t.description}</p>}
            </div>
            {t.action ? (
              <button
                type="button"
                onClick={() => {
                  t.action!.onClick();
                  dismiss(t.id);
                }}
                className="ml-2 h-7 shrink-0 cursor-pointer rounded-md px-2.5 text-ui font-medium text-accent-200 transition hover:bg-on-ink/10"
              >
                {t.action.label}
              </button>
            ) : (
              <span className="w-1" />
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const toast = useContext(ToastContext);
  if (!toast) throw new Error("useToast must be used inside <ToastProvider>");
  return toast;
}
