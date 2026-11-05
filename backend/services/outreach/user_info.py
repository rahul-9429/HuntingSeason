from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from services import career_profiles, user_profiles

_SENIORITY = {
    "entry": "Entry level",
    "senior": "Senior",
    "manager": "Manager",
    "head": "Head of department",
    "director": "Director",
    "vp": "VP",
    "c_suite": "C-suite",
}
_FUNCTION = {"customer_success": "Customer success", "hr": "HR"}
MAX_HIGHLIGHTS = 3


@dataclass(frozen=True)
class UserInfo:
    name: str
    headline: str = ""
    pitch: str = ""
    bio: str = ""
    current_title: str = ""
    current_company: str = ""
    years_experience: int = 0
    seniority: str = ""
    function: str = ""
    skills: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    highlights: tuple[str, ...] = ()
    location: str = ""
    open_to_locations: tuple[str, ...] = ()
    company_sizes: tuple[str, ...] = ()
    linkedin: str = ""
    portfolio: str = ""

    @property
    def has_profile(self) -> bool:
        return bool(self.current_title or self.skills or self.pitch or self.headline)

    def as_prompt(self) -> str:
        lines = [
            f"- {label}: {value}"
            for label, value in (
                ("Name", self.name),
                ("Headline", self.headline),
                ("Pitch", self.pitch),
                ("About", self.bio),
                ("Current title", self.current_title),
                ("Current company", self.current_company),
                ("Years of experience", str(self.years_experience or "")),
                ("Seniority", self.seniority),
                ("Field", self.function),
                ("Top skills", ", ".join(self.skills)),
                ("Industries worked in", ", ".join(self.industries)),
                ("Based in", self.location),
                ("Open to working in", ", ".join(self.open_to_locations)),
                ("Company sizes worked at", ", ".join(self.company_sizes)),
                ("LinkedIn", self.linkedin),
                ("Portfolio", self.portfolio),
            )
            if value
        ]
        lines.extend(f"- Recent achievement: {highlight}" for highlight in self.highlights)
        return "\n".join(lines) or "(not provided)"


async def get_user_info(db: AsyncSession, user_id: int) -> UserInfo:
    general = await user_profiles.get_general(db, user_id)
    experience = await user_profiles.get_experience(db, user_id)
    profile = await career_profiles.get(db, user_id)
    latest = experience.items[0] if experience.items else None
    function = (profile.function if profile else None) or ""
    return UserInfo(
        name=general.name,
        headline=general.headline,
        pitch=general.pitch,
        bio=general.bio,
        current_title=(profile.current_title if profile else None) or (latest.role if latest else ""),
        current_company=general.current_company,
        years_experience=general.years_experience,
        seniority=_SENIORITY.get((profile.seniority if profile else None) or "", ""),
        function=_FUNCTION.get(function, function.replace("_", " ").capitalize()),
        skills=tuple(profile.top_skills) if profile else (),
        industries=tuple(profile.industries) if profile else (),
        highlights=tuple(latest.highlights[:MAX_HIGHLIGHTS]) if latest else (),
        location=(profile.location if profile else None) or general.location,
        open_to_locations=tuple(profile.open_to_locations) if profile else (),
        company_sizes=tuple(
            f"{size.replace(',', '-')} employees" for size in profile.company_size_history
        )
        if profile
        else (),
        linkedin=general.linkedin,
        portfolio=general.portfolio,
    )
