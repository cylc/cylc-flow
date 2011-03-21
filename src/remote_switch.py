#!/usr/bin/env python

# TO DO: ALL REMOTE METHODS TO RETURN RESPONSE AS reset_task_state() DOES.

import Pyro.core
import logging
import sys, os
from CylcError import TaskNotFoundError, TaskStateError
from job_submit import job_submit

class result:
    def __init__( self, success, reason="Action succeeded", value=None ):
        self.success = success
        self.reason = reason
        self.value = value

class remote_switch( Pyro.core.ObjBase ):
    "class to take remote suite control requests" 
    # the task manager can take action on these when convenient.

    def __init__( self, config, clock, suite_dir, pool, failout_id = None ):
        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)

        self.config = config
        self.clock = clock
        self.suite_dir = suite_dir
        self.insert_this = None
        self.failout_id = failout_id

        self.tasks = pool.get_tasks()
        self.pool = pool

        self.process_tasks = False
        self.halt = False
        self.halt_now = False

        # if using the suite block start in the BLOCKED state.
        self.using_block = self.config['use suite blocking']
        self.blocked = True

    def block( self ):
        if not self.using_block:
            return result( False, "This suite is not using blocking" )
        if self.blocked:
            return result( True, "(the suite is already blocked)" )
        self.blocked = True
        return result( True, "the suite has been blocked" )

    def unblock( self ):
        if not self.using_block:
            return result( False, "This suite is not using a safety block" )
        if not self.blocked:
            return result( True, "(the suite is not blocked)" )
        self.blocked = False
        return result( True, "the suite has been unblocked" )

    def nudge( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        # cause the task processing loop to be invoked
        self._warning( "servicing remote nudge request" )
        # just set the "process tasks" indicator
        self.process_tasks = True
        return result( True )

    def reset_task_state( self, task_id, state ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        if task_id == self.failout_id:
            self._reset_failout()
        try:
            self.pool.reset_task_state( task_id, state )
        except TaskStateError, x:
            self._warning( 'Refused remote reset: task state error' )
            return result( False, x.__str__() )
        except TaskNotFoundError, x:
            self._warning( 'Refused remote reset: task not found' )
            return result( False, x.__str__() )
        except Exception, x:
            # do not let a remote request bring the suite down for any reason
            self._warning( 'Remote reset failed: ' + x.__str__() )
            return result( False, "Action failed: "  + x.__str__() )
        else:
            # report success
            self.process_tasks = True
            return result( True )

    def insert( self, ins_id ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        ins_name = self._name_from_id( ins_id )
        if not self._task_type_exists( ins_name ) and \
                ins_name not in self.config[ 'task insertion groups' ]:
            return result( False, "No such task type or group: " + ins_name )
        ins = ins_id
        # insert a new task or task group into the suite
        if ins == self.failout_id:
            # TO DO: DOES EQUALITY TEST FAIL IF INS IS A GROUP?
            self._reset_failout()
        try:
            inserted, rejected = self.pool.insertion( ins )
        except Exception, x:
            self._warning( 'Remote insert failed: ' + x.__str__() )
            return result( False, "Action failed: "  + x.__str__() )
        n_inserted = len(inserted)
        n_rejected = len(rejected)
        if n_inserted == 0:
            msg = "No tasks inserted"
            if n_rejected != 0:
                msg += '\nRejected tasks:'
                for t in rejected:
                    msg += '\n  ' + t
            return result( True, msg )
        elif n_rejected != 0:
            self.process_tasks = True
            msg = 'Inserted tasks:' 
            for t in inserted:
                msg += '\n  ' + t
            msg += '\nRejected tasks:'
            for t in rejected:
                msg += '\n  ' + t
            return result( True, msg )
        elif n_rejected == 0:
            self.process_tasks = True
            msg = 'Inserted tasks:' 
            for t in inserted:
                msg += '\n  ' + t
            return result( True, msg )

    def hold( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        if self.pool.paused():
            return result( True, "(the suite is already paused)" )

        self.pool.set_suite_hold()
        # process, to update state summary
        self.process_tasks = True
        return result( True, "Tasks that are ready to run will not be submitted" )

    def resume( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        if not self.pool.paused() and not self.pool.stopping():
            return result( True, "(the suite is not paused)" )
        self.pool.unset_suite_hold()
        # process, to update state summary
        self.process_tasks = True
        self.halt = False
        return result( True, "Tasks will be submitted when they are ready to run" )

    def set_stop_time( self, ctime ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        self.pool.set_stop_time( ctime )
        # process, to update state summary
        self.process_tasks = True
        return result( True, "The suite will shutdown when all tasks have passed " + ctime )

    def set_hold_time( self, ctime ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        self.pool.set_suite_hold( ctime )
        # process, to update state summary
        self.process_tasks = True
        return result( True, "The suite will pause when all tasks have passed " + ctime )

    def shutdown( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        self.hold()
        self.halt = True
        # process, to update state summary
        self.process_tasks = True
        return result( True, \
                "The suite will shut down after currently running tasks have finished" )

    def shutdown_now( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        self.hold()
        self.halt_now = True
        # process, to update state summary
        self.process_tasks = True
        return result( True, "The suite will shut down immediately" )

    def get_suite_info( self ):
        self._warning( "servicing remote suite info request" )
        owner = os.environ['USER']
        return [ self.config['title'], self.suite_dir, owner ]

    def get_task_list( self ):
        self._warning( "servicing remote task list request" )
        return self.config.get_task_name_list()
 
    def get_task_info( self, task_names ):
        self._warning( "servicing remote task info request" )
        info = {}
        for name in task_names:
            if self._task_type_exists( name ):
                info[ name ] = self.config.get_task_class( name ).describe()
            else:
                info[ name ] = ['ERROR: no such task type']
        return info

    def get_task_requisites( self, in_ids ):
        self._warning( "servicing remote task requisite request")
        in_ids_real = {}
        in_ids_back = {}
        for in_id in in_ids:
            if not self._task_type_exists( in_id ):
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
                # extra info for clocktriggered tasks
                try:
                    extra_info[ 'delayed start time reached' ] = task.start_time_reached( self.clock.get_datetime() ) 
                except AttributeError:
                    # not a clocktriggered task
                    pass
                # extra info for catchup_clocktriggered tasks
                try:
                    extra_info[ task.__class__.name + ' caught up' ] = task.__class__.get_class_var( 'caughtup' )
                except:
                    # not a catchup_clocktriggered task
                    pass
                dump[ in_ids_back[ id ] ] = [ task.prerequisites.dump(), task.outputs.dump(), extra_info ]
        if not found:
            self._warning( '(no tasks found to dump' )
        else:
            return dump
    
    def purge( self, task_id, stop ):
        if self._suite_is_blocked():
            return False, reasons

        if not self._task_type_exists( task_id ):
            return False, "No such task type: " + self._name_from_id( task_id )

        self._warning( "REMOTE: purge " + task_id + ' to ' + stop )
        self.pool.purge( task_id, stop )
        self.process_tasks = True
        return True, "OK"

    def die( self, task_id ):
        if self._suite_is_blocked():
            return False, reasons

        if not self._task_type_exists( task_id ):
            return False, "No such task type: " + self._name_from_id( task_id )

        self._warning( "REMOTE: die: " + task_id )
        self.pool.kill( [ task_id ] )
        self.process_tasks = True
        return True, "OK"

    def die_cycle( self, cycle ):
        if self._suite_is_blocked():
            return False, reasons

        self._warning( "REMOTE: kill cycle: " + cycle )
        self.pool.kill_cycle( cycle )
        self.process_tasks = True
        return True, "OK"

    def spawn_and_die( self, task_id ):
        if self._suite_is_blocked():
            return False, reasons

        if not self._task_type_exists( task_id ):
            return False, "No such task type: " + self._name_from_id( task_id )

        self._warning( "REMOTE: spawn and die: " + task_id )
        self.pool.spawn_and_die( [ task_id ] )
        self.process_tasks = True
        return True, "OK"

    def spawn_and_die_cycle( self, cycle ):
        if self._suite_is_blocked():
            return False, reasons
        self._warning( "REMOTE: spawn and die cycle: " + cycle )
        self.pool.spawn_and_die_cycle( cycle )
        self.process_tasks = True
        return True, "OK"

    def set_verbosity( self, level ):
        if self._suite_is_blocked():
            return False, reasons

        # change the verbosity of all the logs:
        #   debug, info, warning, error, critical
        self._warning( "REMOTE: set verbosity " + level )
        
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
            self._warning( "Illegal logging level: " + level )
            return False, "Illegal logging level: " + level

        self.config[ 'logging level' ] = new_level
        self.log.setLevel( new_level )
        return True, 'OK'

    def should_i_die( self, task_id ):
        if self.halt:
            return True

    # INTERNAL USE METHODS FOLLOW:--------------------------------------

    def _task_type_exists( self, name_or_id ):
        # does a task name or id match a known task type in this suite?
        name = name_or_id
        if '%' in name_or_id:
            name, tag = name.split('%' )
        
        if name in self.config.get_task_name_list():
            return True
        else:
            return False

    def _suite_is_blocked( self ):
        if self.using_block and self.blocked:
            self._warning( "Refusing remote request (suite blocked)" )
            return True
        else:
            return False

    def _name_from_id( self, id ):
        if '%' in id:
            name, tag = id.split('%')
        else:
            name = id
        return name

    def _warning( self, msg ):
        print
        self.log.warning( msg )

    def _reset_failout( self ):
            print "resetting failout on " + self.failout_id
            job_submit.failout_id = None


