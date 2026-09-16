from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "List models available to this Groq API key and confirm GROQ_CHAT_MODEL / GROQ_STT_MODEL exist."

    def handle(self, *args, **options):
        if settings.GROQ_MOCK:
            self.stdout.write(
                self.style.WARNING("GROQ_MOCK=1 — skipping live API check.")
            )
            return

        if not settings.GROQ_API_KEY:
            raise CommandError("GROQ_API_KEY is not set.")

        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY, timeout=30.0)
        try:
            response = client.models.list()
        except Exception as exc:
            raise CommandError(f"Could not list Groq models: {exc}") from exc

        model_ids = {model.id for model in response.data}
        self.stdout.write(f"{len(model_ids)} models available to this API key.")

        for label, model_id in (
            ("GROQ_CHAT_MODEL", settings.GROQ_CHAT_MODEL),
            ("GROQ_STT_MODEL", settings.GROQ_STT_MODEL),
        ):
            if model_id in model_ids:
                self.stdout.write(self.style.SUCCESS(f"{label}={model_id}: OK"))
            else:
                self.stdout.write(
                    self.style.ERROR(f"{label}={model_id}: NOT FOUND in available models")
                )
