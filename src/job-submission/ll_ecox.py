#!/usr/bin/env python

from loadleveler import loadleveler
from ecox import ecox

class ll_ecox( ecox, loadleveler ):
    def __init__( self, task_id, ext_task, task_env, dirs, pre_scr, post_scr, logs, joblog_dir, owner, host ): 
        self.check( task_id, owner, dirs )
        loadleveler.__init__( self, task_id, ext_task, task_env, dirs, pre_scr, post_scr, logs, joblog_dir, owner, host ) 
