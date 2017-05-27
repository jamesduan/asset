from django.contrib import admin
from cmdb.models import WebMenu,SelectDomain


class DynamicWebMenuAdmin(admin.ModelAdmin):
    fields = ('name', 'url', 'top', 'status', 'weight', 'icon', 'new_tab', 'doc_url')
    list_display = ('name', 'id', 'top', 'url', 'status', 'weight',  'icon', 'new_tab', 'doc_url')
    search_fields = ('name',)
    list_filter = ('status', 'top')
    ordering = ('id', 'name', 'top', 'weight')

    def save_model(self, request, obj, form, change):
        # new_name =  request.POST.get('name')
        new_top_id = request.POST.get('top')

        # print "request new name:%s, new top id:%s" %(new_name, new_top_id)
        # print "new top id type:%s" %(type(new_top_id))

        # modify
        if change:
            origin_obj = self.model.objects.get(pk=obj.pk)
            origin_id = origin_obj.id
            # origin_top = origin_obj.top

            # print "origin id:%d" % origin_id
            # top None check
            # if origin_top:
            #     print "origin top_id:%s" % origin_top.id
            # else:
            #     print "origin_top NONE"

            if new_top_id:
                # 'id', 'top_id' check
                # new_top_id is the type of 'unicode'
                new_top_id = int(new_top_id)
                if origin_id == new_top_id:
                    # print "id must not be equal to top_id"
                    raise Exception ("The menu can't be its parent menu by self.")
                    return
            else:
                # print "NONE"
                pass
        # create
        else:
            pass
        # save
        obj.save()


# Register your models here.
admin.site.register(WebMenu, DynamicWebMenuAdmin)

class SelectDomainAdmin(admin.ModelAdmin):
    pass


admin.site.register(SelectDomain, SelectDomainAdmin)


