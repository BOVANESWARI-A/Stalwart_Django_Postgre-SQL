from django.contrib import admin
from .models import (
    AgentClient, AppSetting, ApplicationFile, Candidate, CandidateDocument, EmailLog, Feedback,
    Invitation, JobApplication, Notification, Subscription,
)

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "user", "created_at")
    search_fields = ("full_name", "email", "phone")
    list_filter = ("created_at",)

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "company", "status", "submitted_at", "created_at")
    list_filter = ("company", "status")
    search_fields = ("candidate__email", "candidate__full_name")

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("candidate", "account_type", "paid", "valid_till", "updated_at")
    list_filter = ("account_type", "paid")
    search_fields = ("candidate__email", "candidate__full_name")

@admin.register(AgentClient)
class AgentClientAdmin(admin.ModelAdmin):
    list_display = ("agent", "candidate", "created_at")
    search_fields = ("agent__username", "agent__email", "candidate__email")

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("candidate", "application", "rating", "created_at")
    list_filter = ("rating",)

admin.site.register(ApplicationFile)
admin.site.register(Invitation)
admin.site.register(Notification)
admin.site.register(EmailLog)

admin.site.register(CandidateDocument)
admin.site.register(AppSetting)
