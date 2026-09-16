from django.contrib import admin

from consultations.models import Consultation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "patient",
        "doctor",
        "language",
        "status",
        "turn_count",
        "started_at",
        "completed_at",
    ]
    list_filter = ["status", "language"]
    search_fields = ["patient__username", "doctor__username", "chief_complaint_english"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "consultation", "sender", "language", "slot_target", "created_at"]
    list_filter = ["sender", "language"]
    search_fields = ["text_original", "text_english"]
