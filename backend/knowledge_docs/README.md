# Guideline documents

Place guideline PDFs here, then run the ingest command (see below). Nothing in
this folder is downloaded automatically — add the files yourself.

## Expected documents

- **WHO physical activity guidelines** — WHO guidelines on physical activity
  and sedentary behaviour.
- **ICMR-NIN Dietary Guidelines for Indians** — National Institute of
  Nutrition / Indian Council of Medical Research dietary guidelines.
- **Sleep hygiene guidance** — any reputable sleep hygiene / healthy sleep
  habits guideline document.
- **Hydration guidance** — any reputable guideline on daily water intake /
  hydration.

Any PDF works as long as it's a genuine guideline document with selectable
(non-scanned-image) text — `ingest_guidelines` extracts text per page with
`pypdf`, so a scanned PDF with no text layer will ingest as empty chunks.

## Filenames become the "topic" metadata

Each chunk's `topic` metadata is derived from the PDF's filename (lowercased,
extension stripped, non-alphanumeric characters collapsed to `_`). Name files
so that's meaningful, e.g.:

- `who_physical_activity_guidelines.pdf` -> topic `who_physical_activity_guidelines`
- `icmr_nin_dietary_guidelines.pdf` -> topic `icmr_nin_dietary_guidelines`
- `sleep_hygiene.pdf` -> topic `sleep_hygiene`
- `hydration_guidance.pdf` -> topic `hydration_guidance`

## Ingesting

After adding PDFs here:

```
python manage.py ingest_guidelines
```

Add `--reset` to wipe and rebuild the ChromaDB collection from scratch (use
this after replacing or removing a PDF, not just when adding a new one).
