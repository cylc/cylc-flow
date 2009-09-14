#!/usr/bin/python

from task_base import task_base
from task_modifiers import previous_instance_dependence
from task_modifiers import no_previous_instance_dependence

class forecast_model( previous_instance_dependence, task_base ):
    pass

class free_task( no_previous_instance_dependence, task_base ):
    pass
