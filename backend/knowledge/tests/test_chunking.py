from knowledge.chunking import (
    chunk_text,
    detect_age_group,
    detect_page_heading_age_group,
    slugify_topic,
)


class TestChunkText:
    def test_empty_text_returns_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text(None) == []

    def test_short_text_is_a_single_chunk(self):
        text = "A short guideline sentence."
        assert chunk_text(text) == [text]

    def test_long_text_is_split_with_overlap(self):
        text = "0123456789" * 100  # 1000 chars
        chunks = chunk_text(text, chunk_size=800, overlap=150)
        assert len(chunks) == 2
        assert chunks[0] == text[0:800]
        # second chunk starts at step=650, i.e. 150 chars before the first ends
        assert chunks[1] == text[650:1000]
        # confirm the overlap region is identical text
        assert chunks[0][650:800] == chunks[1][0:150]

    def test_custom_chunk_size_and_overlap(self):
        text = "x" * 50
        chunks = chunk_text(text, chunk_size=20, overlap=5)
        # step = 15: starts at 0, 15, 30 (the chunk from 30 already reaches
        # the end of the 50-char text, so the loop stops there)
        assert len(chunks) == 3
        assert chunks[0] == text[0:20]
        assert chunks[-1] == text[30:50]

    def test_overlap_at_least_chunk_size_does_not_infinite_loop(self):
        text = "y" * 100
        chunks = chunk_text(text, chunk_size=10, overlap=10)
        assert chunks  # just needs to terminate and return something


class TestSlugifyTopic:
    def test_basic_filename(self):
        assert slugify_topic("WHO Physical Activity Guidelines.pdf") == "who_physical_activity_guidelines"

    def test_case_insensitive_extension(self):
        assert slugify_topic("Sleep-Hygiene.PDF") == "sleep_hygiene"

    def test_collapses_punctuation(self):
        assert slugify_topic("ICMR-NIN_Dietary!! Guidelines (2020).pdf") == "icmr_nin_dietary_guidelines_2020"

    def test_empty_stem_falls_back(self):
        assert slugify_topic(".pdf") == "guideline"


class TestDetectAgeGroup:
    def test_children(self):
        assert detect_age_group("This section covers children aged 5-9 years.") == "children"

    def test_adolescents(self):
        assert detect_age_group("Guidance for adolescents aged 13-17.") == "adolescents"

    def test_older_adults_not_misclassified_as_adults(self):
        assert detect_age_group("Older adults (aged 65+ years)") == "older_adults"

    def test_plain_adults(self):
        assert detect_age_group("Adults (aged 18-64 years)") == "adults"

    def test_pregnancy(self):
        assert detect_age_group("Advice for pregnant and postpartum women.") == "pregnancy"

    def test_no_signal_is_unknown(self):
        assert detect_age_group("General health information for everyone.") == "unknown"

    def test_priority_older_adults_before_adults(self):
        # "older adults" contains the substring "adults" - must not match generic adults first.
        assert detect_age_group("older adults") == "older_adults"


class TestDetectPageHeadingAgeGroup:
    def test_heading_line_updates_current_section(self):
        page = "Children and adolescents (aged 5-17 years)\n\nRegular activity supports growth."
        assert detect_page_heading_age_group(page, current="unknown") in ("children", "adolescents")

    def test_no_heading_keeps_current_section(self):
        page = "This is just body text with no section heading at all, describing general advice."
        assert detect_page_heading_age_group(page, current="adults") == "adults"

    def test_long_lines_are_not_treated_as_headings(self):
        # A >100-char line mentioning "children" is body text, not a heading,
        # so it should not override the current section.
        long_line = "Some long paragraph sentence that happens to mention children in passing " * 2
        assert detect_page_heading_age_group(long_line, current="adults") == "adults"

    def test_last_heading_on_page_wins(self):
        page = "Adults (aged 18-64 years)\nsome text\nOlder adults (aged 65+ years)\nmore text"
        assert detect_page_heading_age_group(page, current="unknown") == "older_adults"
