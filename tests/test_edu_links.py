"""Just-in-time education link rules — offline, deterministic."""

from __future__ import annotations

from halo.mci.edu_links import edu_links


def test_canthotomy_triggers() -> None:
    links = edu_links("left eye proptotic with a rock-hard tense orbit, vision going dark")
    assert [link.module_id for link in links] == ["lateral_canthotomy"]
    assert links[0].url == "/edu/modules/lateral_canthotomy/card"
    assert links[0].matched  # the trigger fragment is reported for transparency


def test_organophosphate_triggers() -> None:
    links = edu_links("pinpoint pupils, drooling, muscle fasciculations after plant exposure")
    assert "organophosphate" in {link.module_id for link in links}


def test_perimortem_and_breech() -> None:
    assert edu_links("maternal arrest, start perimortem cesarean")[0].module_id in (
        "perimortem_cesarean",
    )
    assert edu_links("frank breech presenting")[0].module_id == "breech_delivery"


def test_each_module_linked_once() -> None:
    links = edu_links("drooling, pinpoint pupils, organophosphate pesticide exposure")
    ids = [link.module_id for link in links]
    assert ids.count("organophosphate") == 1


def test_plain_trauma_text_triggers_nothing() -> None:
    assert edu_links("ankle inversion injury, x-ray negative, splint applied") == ()


def test_suggestion_only_never_alters_triage() -> None:
    # The rules module exposes only link data — no triage or surge imports.
    import halo.mci.edu_links as mod

    assert not any(name in dir(mod) for name in ("salt_triage", "classify", "surge_plan"))
