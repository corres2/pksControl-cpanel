from django.db import models


class InstallationStatus(models.Model):
    server_name = models.CharField(max_length=120, default='servidor-local')
    app_version = models.CharField(max_length=30, default='0.1.0')
    git_commit = models.CharField(max_length=50, blank=True)
    last_update_at = models.DateTimeField(null=True, blank=True)
    last_update_status = models.CharField(max_length=50, blank=True)
    last_backup_path = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.server_name} - {self.app_version}'
