"""
Startup check for the WeasyPrint PDF dependency. WeasyPrint is imported
lazily everywhere else (see pdf.py) so Django can boot without the
GTK/Pango/cairo native libraries it needs - notably on this project's
Windows dev environment. That laziness means a missing install would
otherwise only surface as a 500 the first time a doctor clicks
"Download PDF". This check makes it visible at every
`runserver`/`check`/`migrate` instead.
"""

from django.core.checks import Warning, register


@register("reports")
def check_weasyprint_available(app_configs, **kwargs):
    try:
        import weasyprint  # noqa: F401
    except OSError as exc:
        # WeasyPrint raises OSError (not ImportError) when it can't dlopen
        # Pango/cairo/GObject - see the OSError message it prints for
        # details on which library is missing.
        return [
            Warning(
                f"WeasyPrint cannot load its native libraries ({exc}) - PDF "
                "report generation is unavailable. Doctors will otherwise "
                "only see this when they click 'Download PDF'.",
                hint=(
                    "Install the GTK/Pango/cairo runtime WeasyPrint needs - "
                    "see README.md for the no-admin MSYS2 route on Windows, "
                    "or set WEASYPRINT_DLL_DIRECTORIES in .env if the "
                    "libraries are already installed somewhere not on PATH."
                ),
                id="reports.W001",
            )
        ]
    return []
