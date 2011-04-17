#!/usr/bin/env python

from ll_raw import ll_raw
from _ecox import ecox

class ll_raw_ecox( ecox, ll_raw ):

    def __init__( self, task_id, ext_task, task_env, dirs, pre_scr, post_scr, logs, joblog_dir, owner, host ): 
        self.check( task_id, owner, dirs )
        ll_raw.__init__( self, task_id, ext_task, task_env, dirs, pre_scr, post_scr, logs, joblog_dir, owner, host ) 
