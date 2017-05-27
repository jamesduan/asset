from django.contrib import admin
from deploy.models import DeployCenterMenu


class DeployCenterMenuAdmin(admin.ModelAdmin):
    pass


admin.site.register(DeployCenterMenu, DeployCenterMenuAdmin)