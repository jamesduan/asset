from django.contrib import admin
from asset.models import Room


class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'comment', 'ycc_code', 'parent',  'architecture_name')


admin.site.register(Room, RoomAdmin)
