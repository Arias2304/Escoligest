from django.contrib import admin

from .models import Conversation, ConversationAdminAccess, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "medic", "created_at")
    search_fields = (
        "patient__username",
        "patient__full_name",
        "medic__username",
        "medic__full_name",
    )
    list_filter = ("created_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at")
    search_fields = ("sender__username", "sender__full_name", "content")
    list_filter = ("created_at",)


@admin.register(ConversationAdminAccess)
class ConversationAdminAccessAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "admin", "granted_by", "granted_at")
    search_fields = (
        "conversation__patient__username",
        "conversation__medic__username",
        "admin__username",
    )
    list_filter = ("granted_at",)
