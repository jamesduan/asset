#!/usr/bin/env python
##
#test s
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assetv2.settingsapi")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
