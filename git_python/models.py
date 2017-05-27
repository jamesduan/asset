from django.db import models
from cmdb.models import App, Room
from django.contrib.auth.models import User


class GitBootShApp(models.Model):
    app = models.OneToOneField(App, parent_link=True, null=False)

    class Meta:
        db_table = u'git_boot_sh_app'


class GitFileType(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    room_property = models.BooleanField()

    class Meta:
        db_table = u'git_file_type'

    def __unicode__(self):
        return self.name


class GitApp(models.Model):
    app = models.ForeignKey(App, null=True)
    type = models.ForeignKey(GitFileType, null=False)
    room = models.ForeignKey(Room, null=True)
    created_by = models.ForeignKey(User, null=False)
    valid = models.BooleanField(default=0)

    class Meta:
        db_table = u'git_app'
        unique_together = (('app', 'type', 'room'),)
