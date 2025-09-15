from django.contrib import admin
from .models import Message

# Register your models here.

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'short_content')
    list_select_related = ('user',)

    def short_content(self, obj):
        return obj.content[:50]
    short_content.short_description = 'Content'