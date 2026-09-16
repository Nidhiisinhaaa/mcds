import pytest
from django.core.management import call_command

from assessment import recommender
from assessment.models import RiskFlag
from knowledge import chroma, retriever
from knowledge.management.commands import ingest_guidelines
from knowledge.tests.pdf_fixtures import build_minimal_pdf


@pytest.fixture
def isolated_chroma(tmp_path, monkeypatch):
    chroma_dir = tmp_path / "chroma_db"
    monkeypatch.setattr(chroma, "CHROMA_DIR", chroma_dir)
    monkeypatch.setattr(chroma, "_client", None)
    retriever._warned_missing_collection = False
    yield chroma_dir
    monkeypatch.setattr(chroma, "_client", None)


@pytest.fixture
def docs_dir(tmp_path, monkeypatch):
    directory = tmp_path / "knowledge_docs"
    directory.mkdir()
    monkeypatch.setattr(ingest_guidelines, "DOCS_DIR", directory)
    return directory


def _flag(consultation, code, severity="medium", reason="test reason"):
    from assessment import risk_rules

    return RiskFlag.objects.create(
        consultation=consultation,
        code=code,
        label=risk_rules.RISK_LABELS.get(code, code),
        severity=severity,
        reason=reason,
    )


@pytest.mark.django_db
class TestFallbackOnly:
    """No PDFs ingested at all -> every flag with a fallback entry should use
    it directly (bypassing the LLM), sourced as "general guidance"."""

    def test_sample_patient_flags_all_use_fallback(self, isolated_chroma, consultation, profile):
        for code in [
            "poor_sleep",
            "sedentary_lifestyle",
            "high_stress",
            "unhealthy_diet",
            "low_water_intake",
            "obesity_risk",
            "hypertension_risk",
        ]:
            _flag(consultation, code)

        created = recommender.generate_recommendations(consultation)

        # obesity_risk -> "weight" and hypertension_risk -> "hypertension" have
        # no entry in fallback_recommendations.json and nothing was retrieved,
        # so they're skipped; the other 5 flags all have fallback content.
        categories = {r.category for r in created}
        assert categories == {"sleep", "exercise", "stress", "diet", "water"}
        assert all(r.sources == ["general guidance"] for r in created)
        assert all(r.text_english for r in created)

    def test_no_profile_returns_empty(self, isolated_chroma, consultation):
        assert recommender.generate_recommendations(consultation) == []

    def test_no_flags_returns_empty(self, isolated_chroma, consultation, profile):
        assert recommender.generate_recommendations(consultation) == []

    def test_red_flag_codes_are_skipped(self, isolated_chroma, consultation, profile):
        _flag(consultation, "chest_pain", severity="high", reason="escalation")
        assert recommender.generate_recommendations(consultation) == []

    def test_translation_applied_for_non_english_consultation(
        self, isolated_chroma, patient_user
    ):
        from assessment.models import LifestyleProfile
        from consultations.models import Consultation

        hindi_consultation = Consultation.objects.create(patient=patient_user, language="hi")
        LifestyleProfile.objects.create(consultation=hindi_consultation)
        _flag(hindi_consultation, "poor_sleep")

        created = recommender.generate_recommendations(hindi_consultation)
        assert len(created) == 1
        item = created[0]
        assert item.text_patient_language.startswith("[hi] ")
        assert item.text_patient_language != item.text_english


@pytest.mark.django_db
class TestRetrievalGrounded:
    def test_flag_with_retrieved_chunks_uses_llm_and_cites_sources(
        self, isolated_chroma, docs_dir, consultation, profile, monkeypatch
    ):
        (docs_dir / "who_physical_activity_guidelines.pdf").write_bytes(
            build_minimal_pdf(
                [
                    "Adults should do at least 150 to 300 minutes of moderate-intensity "
                    "physical activity per week, such as brisk walking."
                ]
            )
        )
        call_command("ingest_guidelines")

        _flag(consultation, "sedentary_lifestyle")

        def fake_chat_json(system, messages, schema, temperature=0.0):
            return schema(
                items=[
                    {
                        "category": "exercise",
                        "text_english": "Walk briskly for at least 150 minutes a week.",
                        "source_refs": ["R1", "R99"],  # R99 does not exist - must be dropped
                    }
                ]
            )

        monkeypatch.setattr("core.services.groq_client.chat_json", fake_chat_json)

        created = recommender.generate_recommendations(consultation)

        assert len(created) == 1
        rec = created[0]
        assert rec.category == "exercise"
        assert rec.text_english == "Walk briskly for at least 150 minutes a week."
        assert rec.sources == [{"file": "who_physical_activity_guidelines.pdf", "page": 1}]

    def test_mixed_retrieval_and_fallback(
        self, isolated_chroma, docs_dir, consultation, profile, monkeypatch
    ):
        (docs_dir / "who_physical_activity_guidelines.pdf").write_bytes(
            build_minimal_pdf(["Aim for 150 to 300 minutes of physical activity a week."])
        )
        call_command("ingest_guidelines")

        _flag(consultation, "sedentary_lifestyle")  # will retrieve real chunks
        _flag(consultation, "poor_sleep")  # nothing ingested for sleep -> fallback

        def fake_chat_json(system, messages, schema, temperature=0.0):
            return schema(
                items=[
                    {
                        "category": "exercise",
                        "text_english": "Aim for 150+ minutes of activity weekly.",
                        "source_refs": ["R1"],
                    }
                ]
            )

        monkeypatch.setattr("core.services.groq_client.chat_json", fake_chat_json)

        created = recommender.generate_recommendations(consultation)
        categories = {r.category for r in created}
        assert categories == {"exercise", "sleep"}

        sleep_item = next(r for r in created if r.category == "sleep")
        assert sleep_item.sources == ["general guidance"]

        exercise_item = next(r for r in created if r.category == "exercise")
        assert exercise_item.sources == [
            {"file": "who_physical_activity_guidelines.pdf", "page": 1}
        ]

    def test_order_field_is_sequential(self, isolated_chroma, consultation, profile):
        _flag(consultation, "poor_sleep")
        _flag(consultation, "low_water_intake")

        created = recommender.generate_recommendations(consultation)
        orders = [r.order for r in created]
        assert orders == sorted(orders)
        assert orders == list(range(len(created)))


class TestDeriveAgeGroup:
    def test_none_defaults_to_adults(self):
        assert recommender.derive_patient_age_group(None) == "adults"

    def test_under_18_is_children_or_adolescents(self):
        assert recommender.derive_patient_age_group(10) == ["children", "adolescents"]
        assert recommender.derive_patient_age_group(17) == ["children", "adolescents"]

    def test_18_to_64_is_adults(self):
        assert recommender.derive_patient_age_group(18) == "adults"
        assert recommender.derive_patient_age_group(64) == "adults"

    def test_65_plus_is_older_adults(self):
        assert recommender.derive_patient_age_group(65) == "older_adults"
        assert recommender.derive_patient_age_group(80) == "older_adults"


@pytest.mark.django_db
class TestAgeGroupMatching:
    """Reproduces the live bug report: a WHO-style PDF with both a
    children/adolescents section and an adults section. An adult patient
    must never receive the children/adolescents content, and a paediatric
    patient must be able to receive it."""

    def _ingest_who_style_pdf(self, docs_dir):
        from knowledge.tests.pdf_fixtures import build_minimal_pdf

        (docs_dir / "who_physical_activity_guidelines.pdf").write_bytes(
            build_minimal_pdf(
                [
                    "Children and adolescents (aged 5-17 years)\n\n"
                    "Greater sedentary behaviour is linked to shorter sleep duration in "
                    "children and adolescents, so screen time should be limited.",
                    "Adults (aged 18-64 years)\n\n"
                    "Adults should aim for a consistent sleep schedule and limit screen "
                    "time before bed to improve sleep quality.",
                ]
            )
        )
        call_command("ingest_guidelines")

    def test_adult_patient_never_gets_child_framed_advice(
        self, isolated_chroma, docs_dir, patient_user, monkeypatch
    ):
        from consultations.models import Consultation
        from assessment.models import LifestyleProfile

        patient_user.patient_profile.age = 40
        patient_user.patient_profile.save()

        self._ingest_who_style_pdf(docs_dir)

        consultation = Consultation.objects.create(patient=patient_user, language="en")
        LifestyleProfile.objects.create(consultation=consultation)
        _flag(consultation, "poor_sleep")

        def fake_chat_json(system, messages, schema, temperature=0.0):
            assert "adult" in system.lower()
            user_content = messages[0]["content"]
            # Only the adults-section chunk should have been retrieved - the
            # children/adolescents chunk must be filtered out entirely.
            assert "children" not in user_content.lower()
            assert "adolescents" not in user_content.lower()
            assert "page 2" in user_content  # the adults-section page
            return schema(
                items=[
                    {
                        "category": "sleep",
                        "text_english": "Keep a consistent sleep schedule and limit screen "
                        "time before bed.",
                        "source_refs": ["R1"],
                    }
                ]
            )

        monkeypatch.setattr("core.services.groq_client.chat_json", fake_chat_json)

        created = recommender.generate_recommendations(consultation)
        assert len(created) == 1
        assert "child" not in created[0].text_english.lower()
        assert "adolescent" not in created[0].text_english.lower()
        assert created[0].sources == [
            {"file": "who_physical_activity_guidelines.pdf", "page": 2}
        ]

    def test_paediatric_patient_receives_child_appropriate_chunks(
        self, isolated_chroma, docs_dir, patient_user, monkeypatch
    ):
        from consultations.models import Consultation
        from assessment.models import LifestyleProfile

        patient_user.patient_profile.age = 14
        patient_user.patient_profile.save()

        self._ingest_who_style_pdf(docs_dir)

        consultation = Consultation.objects.create(patient=patient_user, language="en")
        LifestyleProfile.objects.create(consultation=consultation)
        _flag(consultation, "poor_sleep")

        captured = {}

        def fake_chat_json(system, messages, schema, temperature=0.0):
            captured["system"] = system
            captured["user_content"] = messages[0]["content"]
            return schema(
                items=[
                    {
                        "category": "sleep",
                        "text_english": "Limit screen time in the evening to help with sleep.",
                        "source_refs": ["R1"],
                    }
                ]
            )

        monkeypatch.setattr("core.services.groq_client.chat_json", fake_chat_json)

        created = recommender.generate_recommendations(consultation)
        assert len(created) == 1
        assert "under 18" in captured["system"].lower()
        assert "children" in captured["user_content"].lower()
        assert created[0].sources == [
            {"file": "who_physical_activity_guidelines.pdf", "page": 1}
        ]

    def test_post_check_drops_and_falls_back_when_wrong_age_group_slips_through(
        self, isolated_chroma, consultation, profile, patient_user, monkeypatch
    ):
        """Even if a chunk's age tag is imperfect and the model still writes
        child-framed text, the post-check must catch it."""
        patient_user.patient_profile.age = 40
        patient_user.patient_profile.save()

        # Add a single generic ("unknown"-tagged) chunk directly, so the flag
        # goes through the LLM path rather than falling back immediately.
        collection = chroma.get_or_create_collection()
        collection.upsert(
            ids=["c1"],
            documents=["General guidance on maintaining a healthy sleep routine."],
            metadatas=[{"file": "sleep_hygiene.pdf", "page": 1, "topic": "sleep_hygiene", "age_group": "unknown"}],
        )

        _flag(consultation, "poor_sleep")

        def fake_chat_json(system, messages, schema, temperature=0.0):
            return schema(
                items=[
                    {
                        "category": "sleep",
                        "text_english": "Children should have a consistent bedtime routine.",
                        "source_refs": ["R1"],
                    }
                ]
            )

        monkeypatch.setattr("core.services.groq_client.chat_json", fake_chat_json)

        created = recommender.generate_recommendations(consultation)
        assert len(created) == 1
        assert "child" not in created[0].text_english.lower()
        # Fell back to the static sleep guidance instead.
        assert created[0].sources == ["general guidance"]
