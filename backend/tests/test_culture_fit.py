import pytest

from services.hunt import contact_finder, culture

pytestmark = pytest.mark.anyio

UI_STAGES = ["Seed – Series A", "Growth (Series B–D)", "Public"]


def test_the_bands_cover_the_labels_the_culture_tab_sends():
    assert [culture.band_for(stage) for stage in UI_STAGES] == [
        (1, 200),
        (201, 5000),
        (5001, None),
    ]


def test_an_unknown_stage_label_is_ignored_rather_than_penalising_everyone():
    assert culture.band_for("Whatever stage") is None
    assert culture.fits(["Whatever stage"], 50) is True


def test_a_company_in_a_wanted_stage_fits():
    assert culture.fits(["Seed – Series A"], 1) is True
    assert culture.fits(["Seed – Series A"], 200) is True
    assert culture.fits(["Growth (Series B–D)"], 201) is True
    assert culture.fits(["Public"], 50_000) is True


def test_a_company_outside_every_wanted_stage_does_not_fit():
    assert culture.fits(["Seed – Series A"], 201) is False
    assert culture.fits(["Public"], 5000) is False
    assert culture.fits(["Seed – Series A", "Public"], 1000) is False


def test_several_wanted_stages_are_an_or():
    assert culture.fits(["Seed – Series A", "Public"], 50) is True
    assert culture.fits(["Seed – Series A", "Public"], 50_000) is True


def test_no_preference_and_unknown_headcount_never_penalise():
    assert culture.fits([], 1_000_000) is True
    assert culture.fits(["Seed – Series A"], None) is True


def test_a_contact_at_a_mismatched_company_ranks_lower():
    titles = ["engineering manager"]
    fitting = contact_finder.relevance("Engineering Manager", titles, True, True, True)
    mismatched = contact_finder.relevance("Engineering Manager", titles, True, True, False)

    assert fitting == 100
    assert mismatched == fitting - contact_finder.CULTURE_PENALTY
    assert mismatched > 0


def test_company_fit_never_outranks_a_better_title():
    titles = ["engineering manager"]
    good_title_bad_company = contact_finder.relevance("Engineering Manager", titles, True, True, False)
    bad_title_good_company = contact_finder.relevance("Office Manager", titles, True, True, True)

    assert good_title_bad_company > bad_title_good_company


def test_the_penalty_applies_to_hunter_and_web_contacts_too():
    titles: dict = {"hiring_manager": ["engineering manager"]}
    person = {"title": "Engineering Manager", "email": "a@b.com"}

    fitting = contact_finder.type_by_title(person, titles, True)
    mismatched = contact_finder.type_by_title(person, titles, False)

    assert fitting is not None and mismatched is not None
    assert mismatched[1] == fitting[1] - contact_finder.CULTURE_PENALTY
