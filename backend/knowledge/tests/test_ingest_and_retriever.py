import pytest
from django.core.management import call_command

from knowledge import chroma, retriever
from knowledge.management.commands import ingest_guidelines
from knowledge.tests.pdf_fixtures import build_minimal_pdf


@pytest.fixture
def isolated_chroma(tmp_path, monkeypatch):
    """Point the shared chroma client at a fresh temp directory for this
    test, and reset the module-level singleton before and after so tests
    never see each other's collections."""
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


def _write_fixture_pdf(directory, filename, pages):
    (directory / filename).write_bytes(build_minimal_pdf(pages))


@pytest.mark.django_db
class TestIngestGuidelines:
    def test_ingests_pdf_into_collection(self, isolated_chroma, docs_dir, capsys):
        _write_fixture_pdf(
            docs_dir,
            "who_physical_activity_guidelines.pdf",
            [
                "Adults should do at least 150 to 300 minutes of moderate-intensity "
                "physical activity per week for substantial health benefits.",
                "Limit the amount of time spent being sedentary. Replace sedentary "
                "time with physical activity of any intensity.",
            ],
        )

        call_command("ingest_guidelines")

        output = capsys.readouterr().out
        assert "who_physical_activity_guidelines.pdf: 2 chunks" in output
        assert "Ingested 2 chunks from 1 file(s)" in output

        collection = chroma.get_or_create_collection()
        assert collection.count() == 2

        stored = collection.get()
        assert all(meta["file"] == "who_physical_activity_guidelines.pdf" for meta in stored["metadatas"])
        assert {meta["page"] for meta in stored["metadatas"]} == {1, 2}
        assert all(meta["topic"] == "who_physical_activity_guidelines" for meta in stored["metadatas"])

    def test_no_pdfs_warns_and_does_not_crash(self, isolated_chroma, docs_dir, capsys):
        call_command("ingest_guidelines")
        output = capsys.readouterr().out
        assert "No PDFs found" in output

    def test_missing_docs_dir_warns_and_does_not_crash(self, isolated_chroma, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(ingest_guidelines, "DOCS_DIR", tmp_path / "does_not_exist")
        call_command("ingest_guidelines")
        output = capsys.readouterr().out
        assert "does not exist" in output

    def test_reset_flag_rebuilds_collection(self, isolated_chroma, docs_dir, capsys):
        _write_fixture_pdf(docs_dir, "sleep_hygiene.pdf", ["Keep a consistent sleep schedule every day."])
        call_command("ingest_guidelines")
        assert chroma.get_or_create_collection().count() == 1

        # Replace the PDF with different content and re-ingest with --reset.
        (docs_dir / "sleep_hygiene.pdf").unlink()
        _write_fixture_pdf(
            docs_dir,
            "sleep_hygiene.pdf",
            ["Avoid caffeine in the evening.", "Keep the bedroom dark and cool."],
        )
        call_command("ingest_guidelines", "--reset")

        collection = chroma.get_or_create_collection()
        assert collection.count() == 2


@pytest.mark.django_db
class TestRetriever:
    def test_retrieve_returns_chunks_with_metadata(self, isolated_chroma, docs_dir):
        _write_fixture_pdf(
            docs_dir,
            "who_physical_activity_guidelines.pdf",
            [
                "Adults should do at least 150 to 300 minutes of moderate-intensity "
                "physical activity per week for substantial health benefits."
            ],
        )
        call_command("ingest_guidelines")

        results = retriever.retrieve("physical activity exercise recommendations", k=4)
        assert len(results) == 1
        assert "physical activity" in results[0]["text"]
        assert results[0]["metadata"]["file"] == "who_physical_activity_guidelines.pdf"
        assert results[0]["metadata"]["page"] == 1

    def test_retrieve_with_topic_filter(self, isolated_chroma, docs_dir):
        _write_fixture_pdf(docs_dir, "sleep_hygiene.pdf", ["Keep a consistent sleep schedule."])
        _write_fixture_pdf(
            docs_dir, "hydration_guidance.pdf", ["Drink water regularly throughout the day."]
        )
        call_command("ingest_guidelines")

        results = retriever.retrieve(
            "sleep hygiene recommendations for a consistent schedule", k=4, topic="sleep_hygiene"
        )
        assert len(results) == 1
        assert results[0]["metadata"]["topic"] == "sleep_hygiene"

    def test_retrieve_on_missing_collection_returns_empty_and_does_not_crash(self, isolated_chroma):
        results = retriever.retrieve("anything", k=4)
        assert results == []

    def test_retrieve_on_empty_collection_returns_empty(self, isolated_chroma):
        chroma.get_or_create_collection()  # exists, but nothing ingested
        results = retriever.retrieve("anything", k=4)
        assert results == []


@pytest.mark.django_db
class TestAgeGroupTaggingAndFiltering:
    """Reproduces the live bug: an adult patient's sleep recommendation was
    drawn from the WHO PDF's children/adolescents section."""

    def test_ingest_tags_chunks_by_heading_section(self, isolated_chroma, docs_dir):
        _write_fixture_pdf(
            docs_dir,
            "who_physical_activity_guidelines.pdf",
            [
                "Children and adolescents (aged 5-17 years)\n\n"
                "Children and adolescents should do at least 60 minutes of moderate "
                "to vigorous physical activity daily, mostly aerobic, across the week.",
                "Greater sedentary behaviour is linked to shorter sleep duration in "
                "children and adolescents, and screen time should be limited.",
                "Adults (aged 18-64 years)\n\n"
                "Adults should do at least 150 to 300 minutes of moderate-intensity "
                "physical activity per week for substantial health benefits.",
            ],
        )
        call_command("ingest_guidelines")

        stored = chroma.get_or_create_collection().get()
        by_page = {m["page"]: m["age_group"] for m in stored["metadatas"]}
        assert by_page[1] in ("children", "adolescents")
        assert by_page[2] in ("children", "adolescents")  # inherited - no heading of its own
        assert by_page[3] == "adults"

    def test_adult_retrieval_excludes_child_tagged_chunk(self, isolated_chroma, docs_dir):
        _write_fixture_pdf(
            docs_dir,
            "who_physical_activity_guidelines.pdf",
            [
                "Children and adolescents (aged 5-17 years)\n\n"
                "Greater sedentary behaviour is linked to shorter sleep duration in "
                "children and adolescents."
            ],
        )
        call_command("ingest_guidelines")

        query = "sleep hygiene recommendations for better sleep quality and duration"
        assert retriever.retrieve(query, k=4, age_group="adults") == []

        child_results = retriever.retrieve(query, k=4, age_group=["children", "adolescents"])
        assert len(child_results) == 1
        assert child_results[0]["metadata"]["age_group"] in ("children", "adolescents")

    def test_unknown_tagged_chunk_matches_every_age_group(self, isolated_chroma, docs_dir):
        _write_fixture_pdf(
            docs_dir,
            "hydration_guidance.pdf",
            ["Drink water regularly throughout the day to stay well hydrated."],
        )
        call_command("ingest_guidelines")

        stored = chroma.get_or_create_collection().get()
        assert stored["metadatas"][0]["age_group"] == "unknown"

        query = "daily water intake and hydration recommendations"
        for age_group in ["adults", "older_adults", ["children", "adolescents"]]:
            assert len(retriever.retrieve(query, k=4, age_group=age_group)) == 1
