from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "created_by", "approved_by", "published_at")
    list_filter = ("status", "created_by", "approved_by")
    search_fields = ("title", "summary", "content")
    readonly_fields = ("created_at", "updated_at", "published_at")
