#!/usr/bin/python

import Pyro.core
import task_classes
import logging
import sys, os

class remote_switch( Pyro.core.ObjBase ):
    "class to take remote system control requests" 
    # the task manager can take action on these when convenient.

    def __init__( self, config, pool, failout_id = None ):

        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)

        self.config = config
        self.insert_this = None
        self.failout_id = failout_id

        self.tasks = pool.get_tasks()

        self.pool = pool

        self.process_tasks = False
        self.halt = False
        self.halt_now = False

    def nudge( self ):
        # cause the task processing loop to be invoked
        self.log.warning( "REMOTE: nudge" )
        self.process_tasks = True

    def reset_to_waiting( self, task_id ):
        # reset a task to the waiting state
        self.log.warning( "REMOTE: reset to waiting: " + task_id )
        if task_id == self.failout_id:
            print "resetting failout on " + self.failout_id + " prior to reset"
            os.environ['FAILOUT_ID'] = ""
        self.pool.reset_task( task_id )
        self.process_tasks = True

    def reset_to_ready( self, task_id ):
        # reset a task to the ready state
        self.log.warning( "REMOTE: reset to ready: " + task_id )
        if task_id == self.failout_id:
            print "resetting failout on " + self.failout_id + " prior to reset"
            os.environ['FAILOUT_ID'] = ""
        self.pool.reset_task_to_ready( task_id )
        self.process_tasks = True

    def reset_to_finished( self, task_id ):
        # reset a task to the waiting finished
        self.log.warning( "REMOTE: reset to finished: " + task_id )
        self.pool.reset_task_to_finished( task_id )
        self.process_tasks = True

    def insert( self, ins ):
        # insert a new task or task group into the system
        self.log.warning( "REMOTE: task insertion: " + ins )
        if ins == self.failout_id:
            # TO DO: DOES EQUALITY TEST FAIL IF INS IS A GROUP?
            print "resetting failout on " + self.failout_id + " prior to insertion"
            os.environ['FAILOUT_ID'] = ""
        self.pool.insertion( ins )
        self.process_tasks = True

    def hold( self ):
        self.log.warning( "REMOTE: system hold" )
        self.pool.set_system_hold()

    def resume( self ):
        self.log.warning( "REMOTE: system resume" )
        self.pool.unset_system_hold()
        self.process_tasks = True

    def set_stop_time( self, ctime ):
        self.log.warning( "REMOTE: set stop time" )
        self.pool.set_stop_time( ctime )
 
    def set_hold_time( self, ctime ):
        self.log.warning( "REMOTE: set hold time" )
        self.pool.set_system_hold( ctime )
 
    def shutdown( self ):
        self.log.warning( "REMOTE: halt when running tasks finish" )
        self.hold()
        self.halt = True

    def shutdown_now( self ):
        self.log.warning( "REMOTE: halt NOW" )
        self.hold()
        self.halt_now = True

    def get_config( self, item ):
        self.log.warning( "REMOTE: config item " + item )
        try:
            result = self.config.get( item )
        except:
            self.log.warning( "no such config item: " + item )
        else:
            return result

    def get_sys_info( self ):
        self.log.warning( "REMOTE: system info requested" )
        return [ self.config.get('system_title'), \
                self.config.get('system_def_dir'), \
                self.config.get('system_username'), \
                self.config.get('system_info') ]

    def get_task_info( self, task_names ):
        self.log.warning( "REMOTE: task info: " + ','.join(task_names ))
        info = {}
        for n in task_names:
            try:
                descr = eval( 'task_classes.' + n + '.describe()' )
            except AttributeError:
                info[ n ] = ['ERROR: No Such Task Class']
            else:
                info[ n ] = descr

        return info

    def get_task_requisites( self, task_ids ):
        self.log.warning( "REMOTE: requisite request")

        dump = {}
        found = False
        for task in self.tasks:
            id = task.get_identity()
            if id in task_ids:
                found = True

                extra_info = {}

                # extra info for contact tasks
                try:
                    clock = self.config.get('clock')
                    extra_info[ 'delayed start time reached' ] = task.start_time_reached( clock.get_datetime() ) 
                except AttributeError:
                    # not a contact task
                    pass

                # extra info for catchup_contact tasks
                try:
                    extra_info[ task.__class__.name + ' caught up' ] = task.__class__.get_class_var( 'caughtup' )
                except:
                    # not a catchup_contact task
                    pass

                dump[ id ] = [ task.prerequisites.dump(), task.outputs.dump(), extra_info ]

        if not found:
            self.log.warning( 'No tasks found for the requisite dump request' )
 
        return dump
    
    def purge( self, task_id, stop ):
        self.log.warning( "REMOTE: purge " + task_id + ' to ' + stop )
        self.pool.purge( task_id, stop )
        self.process_tasks = True

    def die( self, task_id ):
        self.log.warning( "REMOTE: die: " + task_id )
        self.pool.kill( [ task_id ] )
        self.process_tasks = True
 
    def spawn_and_die( self, task_id ):
        self.log.warning( "REMOTE: spawn and die: " + task_id )
        self.pool.spawn_and_die( [ task_id ] )
        self.process_tasks = True
 
    def set_verbosity( self, level ):
        # change the verbosity of all the logs:
        #   debug, info, warning, error, critical
        self.log.warning( "REMOTE: set verbosity " + level )
        
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
            self.log.warning( "no such logging level: " + level )
            return

        self.config.set( 'logging_level', new_level )

        # main log
        self.log.setLevel( new_level )

        # task logs
        # If this run is a restart from state dump file, the following
        # assumes that the configured task list is the same as in the
        # state-dump file, which should be the case.

        for task in self.tasks:
            name = 'main.' + task.name
            log = logging.getLogger( name )
            log.setLevel( new_level )
