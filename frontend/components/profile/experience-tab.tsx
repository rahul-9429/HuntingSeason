"use client";

import { FileText, GraduationCap } from "lucide-react";
import { SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { CompanyMark } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { useExperience, useResume } from "@/lib/queries/profile";

export function ExperienceTab() {
  const { data } = useExperience();
  const { data: resume } = useResume();

  if (!data) return <SettingsCardSkeleton />;
  const { items: experience, education } = data;

  return (
    <SettingsCard
      title="Experience timeline"
      description="Contacts who share this history — former colleagues, alumni, same stack — rank higher."
      action={
        resume?.parsed_at && (
          <Badge tone="accent">
            <FileText /> Synced from résumé ·{" "}
            {new Date(resume.parsed_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </Badge>
        )
      }
    >
      {experience.length === 0 && (
        <p className="text-ui text-ink-2">
          Nothing here yet. Upload your résumé on the Résumé tab and your roles show up here.
        </p>
      )}
      <ol>
        {experience.map((item, i) => (
          <li key={item.id} className="relative flex gap-4 pb-8 last:pb-0">
            {i < experience.length - 1 && (
              <span aria-hidden className="absolute bottom-1 left-[17px] top-11 w-px bg-line" />
            )}
            <CompanyMark name={item.company} hue={item.hue} size="lg" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                <h3 className="text-ui font-semibold text-ink">{item.role}</h3>
                <span className="font-mono text-micro text-ink-3">
                  {item.start} — {item.end}
                </span>
              </div>
              <p className="text-ui text-ink-2">{[item.company, item.location].filter(Boolean).join(" · ")}</p>
              <ul className="mt-2.5 space-y-1.5">
                {item.highlights.map((highlight) => (
                  <li key={highlight} className="flex gap-2.5 text-ui leading-relaxed text-ink-2">
                    <span className="mt-[9px] size-1 shrink-0 rounded-full bg-ink-3" />
                    {highlight}
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {item.skills.map((skill) => (
                  <Badge key={skill}>{skill}</Badge>
                ))}
              </div>
            </div>
          </li>
        ))}
      </ol>

      {education && (
        <div className="mt-7 flex items-center gap-4 border-t pt-5">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-sunken text-ink-2">
            <GraduationCap className="size-4" />
          </span>
          <div>
            <p className="text-ui font-semibold text-ink">{education.degree}</p>
            <p className="text-micro text-ink-3">
              {[education.school, education.years].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
      )}
    </SettingsCard>
  );
}
