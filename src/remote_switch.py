#!/usr/bin/env python

import Pyro.core
import logging
import sys, os

from job_submit import job_submit

class remote_switch( Pyro.core.ObjBase ):
    "class to take remote suite control requests" 
    # the task manager can take action on these when convenient.

    def __init__( self, config, clock, suite_dir, owner, pool, failout_id = None ):

        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)

        self.config = config
        self.clock = clock
        self.suite_dir = suite_dir
        self.owner = owner
        self.insert_this = None
        self.failout_id = failout_id

        self.tasks = pool.get_tasks()

        self.pool = pool

        self.process_tasks = False
        self.halt = False
        self.halt_now = False

        # start in UNLOCKED state: locking must be done deliberately so
        # that non-operational users aren't plagued by the lock.
        self.using_lock = self.config['use crude safety lock']
        self.locked = False

        self.owner = os.environ['USER']

    def is_legal( self, user ):
        legal = True
        reasons = []
        if user != self.owner:
            legal = False
            self.warning( "refusing remote request (wrong owner)" )
            reasons.append( "wrong owner: " + self.owner )

        if self.using_lock and self.locked:
            legal = False
            self.warning( "refusing remote request (suite locked)" )
            reasons.append( "SUITE LOCKED" )

        return ( legal, ', '.join( reasons ) )

    def name_from_id( self, id ):
        if '%' in id:
            name, tag = id.split('%')
        else:
            name = id
        return name

    def task_type_exists( self, name_or_id ):
        # does a task name or id match a known task type in this suite?
        name = name_or_id
        if '%' in name_or_id:
            name, tag = name.split('%' )
        
        if name in self.config.get_task_name_list():
            return True
        else:
            return False

    def warning( self, msg ):
        print
        self.log.warning( msg )

    def lock( self, user ):
        if not self.using_lock:
            return False, "This suite is not using a safety lock"
        if user != self.owner:
            self.warning( "refusing remote lock request (wrong owner)" )
            return False, "You are not the suite owner"
        if self.locked:
            return True, "OK (already locked)"
        self.warning( "suite locked by remote request" )
        self.locked = True
        return True, "OK"

    def unlock( self, user ):
        if not self.using_lock:
            return False, "This suite is not using a safety lock"
        if user != self.owner:
            self.warning( "refusing remote unlock request (wrong owner)" )
            return False, "You are not the suite owner"
        if not self.locked:
            return True, "OK (already unlocked)"
        self.warning( "suite unlocked by remote request" )
        self.locked = False
        return True, "OK"

    def nudge( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        # cause the task processing loop to be invoked
        self.warning( "nudging by remote request" )
        self.process_tasks = True
        return True, "OK"

    def reset_failout( self ):
            print "resetting failout on " + self.failout_id
            job_submit.failout_id = None

    def reset_to_waiting( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if not self.task_type_exists( task_id ):
            return False, "No such task type: " + self.name_from_id( task_id )

        # reset a task to the waiting state
        self.warning( "REMOTE: reset to waiting: " + task_id )

        if task_id == self.failout_id:
            self.reset_failout()

        self.pool.reset_task( task_id )
        self.process_tasks = True
        return True, "OK"

    def reset_to_ready( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if not self.task_type_exists( task_id ):
            return False, "No such task type: " + self.name_from_id( task_id )

        # reset a task to the ready state
        self.warning( "REMOTE: reset to ready: " + task_id )
        if task_id == self.failout_id:
            self.reset_failout()

        self.pool.reset_task_to_ready( task_id )
        self.process_tasks = True
        return True, "OK"

    def reset_to_finished( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if not self.task_type_exists( task_id ):
            return False, "No such task type: " + self.name_from_id( task_id )

        # reset a task to the finished state
        self.warning( "REMOTE: reset to finished: " + task_id )
        self.pool.reset_task_to_finished( task_id )
        self.process_tasks = True
        return True, "OK"

    def insert( self, ins_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        ins_name = self.name_from_id( ins_id )

        if not self.task_type_exists( ins_name ) and \
                ins_name not in self.config[ 'task insertion groups' ]:
            return False, "No such task type or group: " + ins_name

        ins = ins_id

        # insert a new task or task group into the suite
        self.warning( "REMOTE: task or group insertion: " + ins )
        if ins == self.failout_id:
            # TO DO: DOES EQUALITY TEST FAIL IF INS IS A GROUP?
            self.reset_failout()

        self.pool.insertion( ins )
        self.process_tasks = True
        return True, "OK"

    def hold( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if self.pool.paused():
            return True, "OK (already paused)"

        self.warning( "REMOTE: suite hold" )
        self.pool.set_suite_hold()
        # process, to update state summary
        self.process_tasks = True
        return True, "OK"

    def resume( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons
        if not self.pool.paused() and not self.pool.stopping():
            return True, "OK (already resumed)"

        self.warning( "REMOTE: suite resume" )
        self.pool.unset_suite_hold()
        # process, to update state summary
        self.process_tasks = True
        self.halt = False
        return True, "OK"

    def set_stop_time( self, ctime, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        self.warning( "REMOTE: set stop time" )
        self.pool.set_stop_time( ctime )
        # process, to update state summary
        self.process_tasks = True
        return True, "OK"

    def set_hold_time( self, ctime, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        self.warning( "REMOTE: set hold time" )
        self.pool.set_suite_hold( ctime )
        # process, to update state summary
        self.process_tasks = True
        return True, "OK"

    def shutdown( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        self.warning( "REMOTE: halt when running tasks finish" )
        self.hold( user )
        self.halt = True
        # process, to update state summary
        self.process_tasks = True
        return True, "OK"

    def shutdown_now( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        self.warning( "REMOTE: halt NOW" )
        self.hold( user )
        self.halt_now = True
        # process, to update state summary
        self.process_tasks = True
        return True, "OK"

    def get_config( self, item ):
        self.warning( "REMOTE: config item " + item )
        try:
            result = self.config[ item ]
        except:
            self.warning( "no such config item: " + item )
        else:
            return result

    def get_suite_info( self ):
        self.warning( "REMOTE: suite info requested" )
        return [ self.config['title'], \
                self.suite_dir, \
                self.owner ]

    def get_task_list( self ):
        self.warning( "REMOTE: task list requested" )
        return self.config.get_task_name_list()
 
    def get_task_info( self, task_names ):
        self.warning( "REMOTE: task info: " + ','.join(task_names ))
        info = {}
        for name in task_names:
            if self.task_type_exists( name ):
                info[ name ] = self.config.get_task_class( name ).describe()
            else:
                info[ name ] = ['ERROR: no such task type']
        return info

    def get_task_requisites( self, in_ids ):
        self.warning( "REMOTE: task requisite dump request")

        in_ids_real = {}
        in_ids_back = {}
        for in_id in in_ids:
            if not self.task_type_exists( in_id ):
                continue
            real_id = in_id
            in_ids_real[ in_id ] = real_id
            in_ids_back[ real_id ] = in_id

        dump = {}
        found = False
        for task in self.tasks:
            # loop through the suite task list
            id = task.id

            if id in in_ids_back:

                found = True
                extra_info = {}

                # extra info for contact tasks
                try:
                    extra_info[ 'delayed start time reached' ] = task.start_time_reached( self.clock.get_datetime() ) 
                except AttributeError:
                    # not a contact task
                    pass

                # extra info for catchup_contact tasks
                try:
                    extra_info[ task.__class__.name + ' caught up' ] = task.__class__.get_class_var( 'caughtup' )
                except:
                    # not a catchup_contact task
                    pass

                dump[ in_ids_back[ id ] ] = [ task.prerequisites.dump(), task.outputs.dump(), extra_info ]

        if not found:
            self.warning( 'No tasks found to dump' )
 
        return dump
    
    def purge( self, task_id, stop, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if not self.task_type_exists( task_id ):
            return False, "No such task type: " + self.name_from_id( task_id )

        self.warning( "REMOTE: purge " + task_id + ' to ' + stop )
        self.pool.purge( task_id, stop )
        self.process_tasks = True
        return True, "OK"

    def die( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if not self.task_type_exists( task_id ):
            return False, "No such task type: " + self.name_from_id( task_id )

        self.warning( "REMOTE: die: " + task_id )
        self.pool.kill( [ task_id ] )
        self.process_tasks = True
        return True, "OK"

    def die_cycle( self, cycle, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        self.warning( "REMOTE: kill cycle: " + cycle )
        self.pool.kill_cycle( cycle )
        self.process_tasks = True
        return True, "OK"

    def spawn_and_die( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        if not self.task_type_exists( task_id ):
            return False, "No such task type: " + self.name_from_id( task_id )

        self.warning( "REMOTE: spawn and die: " + task_id )
        self.pool.spawn_and_die( [ task_id ] )
        self.process_tasks = True
        return True, "OK"

    def spawn_and_die_cycle( self, cycle, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons
        self.warning( "REMOTE: spawn and die cycle: " + cycle )
        self.pool.spawn_and_die_cycle( cycle )
        self.process_tasks = True
        return True, "OK"

    def set_verbosity( self, level, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return False, reasons

        # change the verbosity of all the logs:
        #   debug, info, warning, error, critical
        self.warning( "REMOTE: set verbosity " + level )
        
        if level == 'debug':
            new_level = logging.DEBUG
        elif level == 'info':
            new_level = logging.INFO
        elif level == 'warning':
            new_level = logging.WARNING
        elif level == 'error':
            new_level = logging.ERROR
        elif level == 'critical':
            new_level = logging.CRITICAL
        else:
            self.warning( "Illegal logging level: " + level )
            return False, "Illegal logging level: " + level

        self.config[ 'logging level' ] = new_level
        self.log.setLevel( new_level )
        return True, 'OK'

    def should_i_die( self, task_id ):
        if self.halt:
            return True
