"""
Seeds local/demo data: 1 doctor and 3 patients, each with one consultation
covering a different scenario (Poor-band, healthy Good-band, escalated). Safe
to re-run - existing demo accounts (by username) are deleted and recreated
first.

Lifestyle values and messages are written directly rather than produced by
the extractor: under GROQ_MOCK, chat_json calls have no fixture for
ExtractionResult (see core/services/groq_client.py's _mock_schema_instance),
so they'd just return the schema's bare defaults - none of the profile
fields would actually get filled. Writing the profile directly and then
calling assessment.pipeline.run_analysis() exercises the REAL deterministic
scoring/risk-flag/NLP pipeline (nothing here is faked) while still producing
data that matches a specific, chosen scenario for the demo.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import PatientProfile, User
from assessment import pipeline
from assessment.engine import red_flags
from assessment.models import LifestyleProfile
from consultations.models import Consultation, Message

DOCTOR_USERNAME = "doctor"
DOCTOR_PASSWORD = "demo1234"
DEMO_PASSWORD = "demo1234"


class Command(BaseCommand):
    help = "Seed demo data: 1 doctor, 3 patients, 3 consultations (Poor / Good / Escalated)."

    def handle(self, *args, **options):
        # Force mock mode for this command regardless of what backend/.env
        # has GROQ_MOCK set to - same technique as config/test_settings.py,
        # for the same reason: settings.GROQ_MOCK is read fresh via attribute
        # access on the live django.conf.settings object by every Groq call,
        # so reassigning it here (after Django has already started) works,
        # while setting the env var at this point would be too late.
        settings.GROQ_MOCK = True

        self._delete_existing_demo_data()

        doctor = self._create_doctor()
        poor_patient = self._seed_poor_band_patient()
        healthy_patient = self._seed_healthy_hindi_patient()
        escalated_patient = self._seed_escalated_patient()

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded.\n"))
        self._print_credentials(doctor, [poor_patient, healthy_patient, escalated_patient])

    # -- setup / teardown ---------------------------------------------------

    def _delete_existing_demo_data(self):
        usernames = [
            DOCTOR_USERNAME,
            "patient_poor",
            "patient_healthy",
            "patient_escalated",
        ]
        deleted, _ = User.objects.filter(username__in=usernames).delete()
        if deleted:
            self.stdout.write(f"Removed {deleted} existing demo record(s) before reseeding.")

    def _create_doctor(self):
        doctor = User(
            username=DOCTOR_USERNAME,
            role=User.Role.DOCTOR,
            first_name="Asha",
            last_name="Verma",
        )
        doctor.set_password(DOCTOR_PASSWORD)
        doctor.save()
        return doctor

    def _create_patient(self, username, *, full_name, age, sex, height_cm, weight_kg, language):
        user = User(username=username, role=User.Role.PATIENT)
        user.set_password(DEMO_PASSWORD)
        user.save()
        PatientProfile.objects.create(
            user=user,
            full_name=full_name,
            age=age,
            sex=sex,
            height_cm=height_cm,
            weight_kg=weight_kg,
            preferred_language=language,
            consent_given_at=timezone.now(),
        )
        return user

    def _message(self, consultation, sender, text_original, text_english, language, slot_target=None):
        return Message.objects.create(
            consultation=consultation,
            sender=sender,
            text_original=text_original,
            text_english=text_english,
            language=language,
            slot_target=slot_target,
        )

    # -- scenario 1: Phase 3 sample patient (English, Poor band) ------------

    def _seed_poor_band_patient(self):
        patient = self._create_patient(
            "patient_poor",
            full_name="Ramesh Kumar",
            age=45,
            sex="male",
            height_cm=170,
            weight_kg=80,
            language="en",
        )
        consultation = Consultation.objects.create(
            patient=patient,
            language="en",
            status=Consultation.Status.IN_PROGRESS,
            chief_complaint_original="I've had fatigue for 2 weeks and mild headaches, no fever.",
            chief_complaint_english="I've had fatigue for 2 weeks and mild headaches, no fever.",
        )
        qa = [
            ("sleep", "How many hours do you usually sleep at night?", "I sleep about 5 hours a night."),
            ("exercise", "How much do you exercise each week?", "I don't really exercise at all."),
            ("diet", "How would you describe your typical diet?", "I eat fast food most days, it's convenient."),
            ("water", "How much water do you drink a day?", "Maybe 1 litre, I often forget to drink water."),
            ("stress", "How would you rate your day-to-day stress?", "It's high, work has been a lot lately."),
            ("sitting", "How many hours a day do you spend sitting?", "About 9 hours, I have a desk job."),
            ("smoking", "Do you smoke?", "No, I don't smoke."),
            ("alcohol", "How often do you drink alcohol?", "Occasionally, maybe once or twice a month."),
        ]
        self._run_qa_conversation(consultation, qa, "en")

        profile = LifestyleProfile.objects.create(
            consultation=consultation,
            sleep_hours=5.0,
            exercise_days_per_week=0,
            exercise_minutes_per_session=None,
            diet_pattern="frequent_fast_food",
            water_litres_per_day=1.0,
            stress_level="high",
            sitting_hours_per_day=9.0,
            smoking_status="none",
            alcohol_frequency="occasional",
        )

        self._message(
            consultation,
            Message.Sender.AI,
            "Thank you for answering the lifestyle questions - your answers and a wellness "
            "summary are now ready for your doctor to review.",
            "Thank you for answering the lifestyle questions - your answers and a wellness "
            "summary are now ready for your doctor to review.",
            "en",
        )
        consultation.status = Consultation.Status.COMPLETED
        consultation.completed_at = timezone.now()
        consultation.save(update_fields=["status", "completed_at"])

        pipeline.run_analysis(consultation)
        self.stdout.write(
            f"Seeded consultation #{consultation.id} for patient_poor "
            f"(expected: Poor band, score 34)."
        )
        return patient

    # -- scenario 2: healthy Hindi-speaking patient (Good band, 80+) --------

    def _seed_healthy_hindi_patient(self):
        patient = self._create_patient(
            "patient_healthy",
            full_name="Sunita Sharma",
            age=29,
            sex="female",
            height_cm=165,
            weight_kg=58,
            language="hi",
        )
        consultation = Consultation.objects.create(
            patient=patient,
            language="hi",
            status=Consultation.Status.IN_PROGRESS,
            chief_complaint_original="Mujhe halki thakaan hai, lekin bas ek routine checkup ke liye aayi hoon.",
            chief_complaint_english="I have mild fatigue, but I mainly came in for a routine checkup.",
        )
        qa = [
            (
                "sleep",
                "Aap raat mein kitne ghante sote hain?",
                "How many hours do you sleep at night?",
                "Main roz raat ko 7-8 ghante sona hoon.",
                "I sleep 7-8 hours every night.",
            ),
            (
                "exercise",
                "Aap hafte mein kitni baar exercise karte hain?",
                "How often do you exercise each week?",
                "Main hafte mein 5 din, roz 40 minute walk ya yoga karti hoon.",
                "I exercise 5 days a week, 40 minutes each day of walking or yoga.",
            ),
            (
                "diet",
                "Aapka khana kaisa hota hai?",
                "How would you describe your diet?",
                "Main ghar ka sadha, santulit khana khati hoon.",
                "I eat home-cooked, balanced meals.",
            ),
            (
                "water",
                "Aap din mein kitna paani peete hain?",
                "How much water do you drink a day?",
                "Main roz karib 2.5 litre paani peeti hoon.",
                "I drink about 2.5 litres of water a day.",
            ),
            (
                "stress",
                "Aapka roz ka stress level kaisa hai?",
                "How would you rate your day-to-day stress?",
                "Kaafi kam, main apna kaam aaram se manage kar leti hoon.",
                "Quite low, I manage my work comfortably.",
            ),
            (
                "sitting",
                "Aap din mein kitne ghante baithte hain?",
                "How many hours a day do you spend sitting?",
                "Karib 5 ghante, main beech beech mein utthti rehti hoon.",
                "About 5 hours, I get up and move around in between.",
            ),
            (
                "smoking",
                "Kya aap dhoomrapan karte hain?",
                "Do you smoke?",
                "Nahi, main dhoomrapan nahi karti.",
                "No, I don't smoke.",
            ),
            (
                "alcohol",
                "Aap kitni baar sharab peete hain?",
                "How often do you drink alcohol?",
                "Main sharab bilkul nahi peeti.",
                "I don't drink alcohol at all.",
            ),
        ]
        for slot, q_hi, q_en, a_hi, a_en in qa:
            self._message(consultation, Message.Sender.AI, q_hi, q_en, "hi", slot_target=slot)
            self._message(consultation, Message.Sender.PATIENT, a_hi, a_en, "hi")

        LifestyleProfile.objects.create(
            consultation=consultation,
            sleep_hours=7.5,
            exercise_days_per_week=5,
            exercise_minutes_per_session=40,
            diet_pattern="balanced",
            water_litres_per_day=2.5,
            stress_level="low",
            sitting_hours_per_day=5.0,
            smoking_status="none",
            alcohol_frequency="none",
        )

        closing_en = (
            "Thank you for answering the lifestyle questions - your answers and a wellness "
            "summary are now ready for your doctor to review."
        )
        closing_hi = (
            "Lifestyle sawaalon ke jawab dene ke liye dhanyavaad - aapke jawab aur wellness "
            "summary ab aapke doctor ke review ke liye taiyaar hain."
        )
        self._message(consultation, Message.Sender.AI, closing_hi, closing_en, "hi")
        consultation.status = Consultation.Status.COMPLETED
        consultation.completed_at = timezone.now()
        consultation.save(update_fields=["status", "completed_at"])

        pipeline.run_analysis(consultation)
        self.stdout.write(
            f"Seeded consultation #{consultation.id} for patient_healthy "
            f"(expected: Good band, score 80+)."
        )
        return patient

    # -- scenario 3: escalated chest-pain case -------------------------------

    def _seed_escalated_patient(self):
        patient = self._create_patient(
            "patient_escalated",
            full_name="Vikram Singh",
            age=52,
            sex="male",
            height_cm=175,
            weight_kg=82,
            language="en",
        )
        consultation = Consultation.objects.create(
            patient=patient,
            language="en",
            status=Consultation.Status.IN_PROGRESS,
        )
        message = self._message(
            consultation,
            Message.Sender.PATIENT,
            "I have chest pain and it's getting worse.",
            "I have chest pain and it's getting worse.",
            "en",
        )
        consultation.chief_complaint_original = message.text_original
        consultation.chief_complaint_english = message.text_english
        consultation.save(update_fields=["chief_complaint_original", "chief_complaint_english"])

        # The real code path for an emergency keyword match: creates the
        # RiskFlag, escalates the consultation, and sends the calm
        # in-person-care message - deliberately does NOT call run_analysis
        # (see assessment/pipeline.py's docstring: a real escalation stops
        # the questionnaire immediately, so there's no lifestyle data to
        # score and no recommendations to generate).
        red_flags.trigger(consultation, ["chest_pain"], message)

        self.stdout.write(
            f"Seeded consultation #{consultation.id} for patient_escalated "
            f"(expected: Escalated, chest_pain risk flag, no score/recommendations)."
        )
        return patient

    def _run_qa_conversation(self, consultation, qa, language):
        for slot, question, answer in qa:
            self._message(consultation, Message.Sender.AI, question, question, language, slot_target=slot)
            self._message(consultation, Message.Sender.PATIENT, answer, answer, language)

    # -- output ---------------------------------------------------------------

    def _print_credentials(self, doctor, patients):
        self.stdout.write("Demo credentials (username / password):")
        self.stdout.write(f"  doctor   {DOCTOR_USERNAME} / {DOCTOR_PASSWORD}")
        for patient in patients:
            self.stdout.write(f"  patient  {patient.username} / {DEMO_PASSWORD}")
