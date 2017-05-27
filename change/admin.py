from django.contrib import admin
from change.models import Type, Action,ExceptionReport
from cmdb.models import DdDomain


# admin.autodiscover()
# class LevelAdmin(admin.ModelAdmin):
# 	pass

# admin.site.register(Level, LevelAdmin)

class TypeAdmin(admin.ModelAdmin):
    # using = 'change_db'
    pass


admin.site.register(Type, TypeAdmin)


class ActionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'get_level_name', )


admin.site.register(Action, ActionAdmin)

class ExceptionReportAdmin(admin.ModelAdmin):
    list_display = ('cname', 'type','owner','owner_domain','status', 'fileds','use_db')
    search_fields = ('cname','type')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner_domain":
            kwargs["queryset"] =DdDomain.objects.filter(enable=0)
        return super(ExceptionReportAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
    pass

admin.site.register(ExceptionReport, ExceptionReportAdmin)
