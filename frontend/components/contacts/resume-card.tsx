"use client";

import { Check, CircleAlert, CloudUpload, FileText, LoaderCircle } from "lucide-react";
import { useRef, useState } from "react";
import { LoadError } from "@/components/shared/load-error";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useResume, useUploadResume } from "@/lib/queries/profile";
import type { Resume } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_BYTES = 5 * 1024 * 1024;

const shortDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

function ResumeSkeleton({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("animate-pulse space-y-3 rounded-xl border-2 border-line-strong bg-surface p-5", className)}>
      <div className="h-4 w-20 rounded bg-sunken" />
      <div className="h-14 rounded-lg bg-sunken" />
      <div className="h-24 rounded-lg bg-sunken/70" />
    </div>
  );
}

interface ResumeCardProps {
  className?: string;
  /** Called once a newly uploaded résumé has been read. */
  onParsed?: (resume: Resume) => void;
}

export function ResumeCard({ className, onParsed }: ResumeCardProps) {
  const { data: resume, isError, refetch } = useResume();
  const upload = useUploadResume();
  const [progress, setProgress] = useState(0);
  const [freshSkills, setFreshSkills] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  if (isError) return <LoadError what="your résumé" onRetry={() => refetch()} className={className} />;
  if (resume === undefined) return <ResumeSkeleton className={className} />;

  const skills = resume?.profile?.top_skills ?? [];
  const parsing = resume?.status === "parsing";
  const uploading = upload.isPending && !parsing;
  const busy = upload.isPending || parsing;
  const shownError = error ?? (!busy && resume?.status === "failed" ? resume.error : null);

  function acceptFile(file: File) {
    if (!/\.pdf$/i.test(file.name)) {
      setError(`“${file.name}” isn't a PDF. Export your résumé as a PDF and try again.`);
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("That file is over 5 MB — try exporting a lighter PDF.");
      return;
    }
    setError(null);
    setProgress(0);
    const before = new Set(skills.map((s) => s.toLowerCase()));
    upload.mutate(
      { file, onProgress: setProgress },
      {
        onSuccess: (parsed) => {
          if (parsed.status === "failed") {
            setError(parsed.error ?? "We couldn't read that file — try exporting it again.");
            return;
          }
          const added = (parsed.profile?.top_skills ?? []).filter((s) => !before.has(s.toLowerCase()));
          setFreshSkills(new Set(added));
          toast({ title: "Résumé read", description: "Your profile is updated and company search is personalized" });
          onParsed?.(parsed);
        },
      },
    );
  }

  return (
    <section id="resume" className={cn("scroll-mt-6 rounded-xl border-2 border-line-strong bg-surface", className)}>
      <div className="px-5 pt-5 pb-5">
        <div className="flex items-center justify-between">
          <h2 className="text-ui font-semibold text-ink">Résumé</h2>
          <span className="text-micro text-ink-3">Personalizes company search</span>
        </div>

        {resume && (
          <div className="mt-3 flex items-center gap-3 rounded-lg border bg-canvas/60 p-2.5">
            <span className="grid size-8 shrink-0 place-items-center rounded-md bg-surface ring-1 ring-line">
              <FileText className="size-4 text-ink-2" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-ui font-medium text-ink">{resume.file_name}</p>
              <p className="text-micro text-ink-3">
                {resume.status === "parsed" && resume.parsed_at
                  ? `Read ${shortDate(resume.parsed_at)}`
                  : resume.status === "parsing"
                    ? "Reading…"
                    : "Couldn't read this file"}
              </p>
            </div>
            {resume.status === "parsed" && (
              <Badge tone="accent" className="ml-auto">
                <Check /> Read
              </Badge>
            )}
          </div>
        )}

        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files[0];
            if (file && !busy) acceptFile(file);
          }}
          className={cn(
            "mt-3 rounded-lg border border-dashed px-4 py-5 transition-colors",
            dragging ? "border-accent-500 bg-accent-50" : "border-line-strong bg-canvas/40",
            busy && "border-solid bg-surface",
          )}
        >
          {uploading && (
            <div>
              <div className="flex items-center gap-2 text-ui">
                <FileText className="size-3.5 shrink-0 text-ink-3" />
                <span className="truncate font-medium text-ink">{upload.variables?.file.name}</span>
                <span className="ml-auto font-mono text-micro tabular-nums text-ink-3">{progress}%</span>
              </div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-sunken">
                <div
                  className="h-full rounded-full bg-accent-500 transition-[width] duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-2 text-micro text-ink-3">Uploading…</p>
            </div>
          )}

          {parsing && (
            <div aria-live="polite" className="flex items-start gap-2.5 text-ui text-ink">
              <LoaderCircle className="mt-0.5 size-3.5 shrink-0 animate-spin text-accent-700" />
              <div>
                <p>Reading your résumé…</p>
                <p className="mt-0.5 text-micro text-ink-3">
                  Pulling out your title, seniority, skills and industries. Usually under a minute.
                </p>
              </div>
            </div>
          )}

          {!busy && (
            <div className="text-center">
              <CloudUpload className={cn("mx-auto size-5", dragging ? "text-accent-700" : "text-ink-3")} />
              <p className="mt-2 text-ui text-ink">
                {dragging ? (
                  <span className="font-medium text-accent-700">Release to upload</span>
                ) : (
                  <>
                    <span className="font-medium">{resume ? "Drop a new version" : "Drop your résumé"}</span> or{" "}
                    <button
                      type="button"
                      onClick={() => inputRef.current?.click()}
                      className="cursor-pointer font-medium text-accent-700 underline decoration-accent-300 underline-offset-2 hover:decoration-accent-600"
                    >
                      browse
                    </button>
                  </>
                )}
              </p>
              <p className="mt-0.5 text-micro text-ink-3">PDF · up to 5 MB</p>
            </div>
          )}

          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            tabIndex={-1}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) acceptFile(file);
              e.target.value = "";
            }}
          />
        </div>

        {shownError && (
          <p role="alert" className="mt-2 flex items-start gap-1.5 text-micro text-rose-700 dark:text-rose-400">
            <CircleAlert className="mt-px size-3.5 shrink-0" />
            {shownError}
          </p>
        )}
      </div>

      {skills.length > 0 && !busy && (
        <div className="border-t px-5 py-4">
          <p className="text-micro font-medium text-ink-3">Top skills</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {skills.map((skill, i) => {
              const fresh = freshSkills.has(skill);
              return (
                <span
                  key={skill}
                  style={fresh ? { animationDelay: `${i * 70}ms` } : undefined}
                  className={cn(
                    "inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-micro",
                    fresh ? "animate-pop border-accent-300 bg-accent-50 text-accent-800" : "bg-surface text-ink",
                  )}
                >
                  {skill}
                  {fresh && <span className="text-[10px] font-medium text-accent-700">new</span>}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
