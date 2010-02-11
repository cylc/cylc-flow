#!/usr/bin/python

from task_base import task_base
from mod_pid import pid
from mod_nopid import nopid

class forecast_model( pid, task_base ):
    # task class with previous instance dependence
    pass

class free_task( nopid, task_base ):
    # task class with no previous instance dependence
    pass
