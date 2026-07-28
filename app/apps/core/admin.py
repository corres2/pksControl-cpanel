from django.contrib import admin
from .models import InstallationStatus


@admin.register(InstallationStatus)
class InstallationStatusAdmin(admin.ModelAdmin):
    list_display = ('server_name', 'app_version', 'git_commit', 'last_update_at', 'last_update_status')
    readonly_fields = ('created_at', 'updated_at')
