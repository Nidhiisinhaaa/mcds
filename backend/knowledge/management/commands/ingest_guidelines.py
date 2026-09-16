from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge import chroma
from knowledge.chunking import chunk_text, detect_age_group, detect_page_heading_age_group, slugify_topic

DOCS_DIR = Path(settings.BASE_DIR) / "knowledge_docs"


class Command(BaseCommand):
    help = (
        "Extract text from PDFs in backend/knowledge_docs/, chunk it, and store "
        "it in the persistent ChromaDB 'guidelines' collection."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the existing 'guidelines' collection and rebuild it from scratch.",
        )

    def handle(self, *args, **options):
        import pypdf

        if options["reset"]:
            try:
                chroma.get_client().delete_collection(chroma.COLLECTION_NAME)
                self.stdout.write("Deleted existing 'guidelines' collection.")
            except Exception:
                pass  # nothing to delete yet - fine

        collection = chroma.get_or_create_collection()

        if not DOCS_DIR.exists():
            self.stdout.write(
                self.style.WARNING(f"{DOCS_DIR} does not exist - nothing to ingest.")
            )
            return

        pdf_paths = sorted(p for p in DOCS_DIR.iterdir() if p.suffix.lower() == ".pdf")
        if not pdf_paths:
            self.stdout.write(
                self.style.WARNING(f"No PDFs found in {DOCS_DIR} - nothing to ingest.")
            )
            return

        total_chunks = 0
        for pdf_path in pdf_paths:
            file_chunks = self._ingest_pdf(pdf_path, pypdf)
            if file_chunks:
                ids, documents, metadatas = zip(*file_chunks)
                collection.upsert(ids=list(ids), documents=list(documents), metadatas=list(metadatas))
            self.stdout.write(f"{pdf_path.name}: {len(file_chunks)} chunks")
            total_chunks += len(file_chunks)

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingested {total_chunks} chunks from {len(pdf_paths)} file(s) "
                f"into '{chroma.COLLECTION_NAME}' at {chroma.CHROMA_DIR}."
            )
        )

    def _ingest_pdf(self, pdf_path: Path, pypdf_module):
        topic = slugify_topic(pdf_path.name)
        try:
            reader = pypdf_module.PdfReader(str(pdf_path))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"{pdf_path.name}: could not read PDF ({exc})"))
            return []

        file_chunks = []
        current_age_group = "unknown"
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            # A heading on this page (e.g. "Older adults (aged 65+ years)")
            # carries forward to the pages that follow it too, until the
            # next heading changes it.
            current_age_group = detect_page_heading_age_group(page_text, current_age_group)

            for chunk_index, chunk in enumerate(chunk_text(page_text)):
                chunk_id = f"{pdf_path.stem}_p{page_number}_c{chunk_index}"
                # A chunk's own wording (e.g. it happens to say "adults")
                # takes precedence over the inherited section heading;
                # otherwise it inherits the current section's age group.
                chunk_age_group = detect_age_group(chunk)
                if chunk_age_group == "unknown":
                    chunk_age_group = current_age_group
                metadata = {
                    "file": pdf_path.name,
                    "page": page_number,
                    "topic": topic,
                    "age_group": chunk_age_group,
                }
                file_chunks.append((chunk_id, chunk, metadata))

        return file_chunks
