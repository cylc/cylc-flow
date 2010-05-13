#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

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

        self.locked = True

        self.owner = os.environ['USER']

        self.process_task_names()

    def is_legal( self, user ):
        legal = True
        reasons = []
        if user != self.owner:
            legal = False
            self.warning( "refusing task reset request (wrong owner)" )
            reasons.append( "system owner: " + self.owner )
        if self.locked:
            legal = False
            self.warning( "REMOTE: refusing task reset request (locked)" )
            reasons.append( "SYSTEM LOCKED" )

        return ( legal, ', '.join( reasons ) )


    def warning( self, msg ):
        print
        self.log.warning( msg )

    def lock( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "system locked by remote request" )
        self.locked = True
        return "System locked"

    def unlock( self, user ):
        if user != self.owner:
            return "ILLEGAL OPERATION: This system is owned by " + self.owner

        if not self.locked:
            self.warning( "REMOTE: system unlock requested (already unlocked)" )
            return "System already unlocked"

        else:
            self.warning( "system unlocked by remote request" )
            self.locked = False
            return "System unlocked"


    def nudge( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        # cause the task processing loop to be invoked
        self.warning( "nudging by remote request" )
        self.process_tasks = True
        return "Done"

    def reset_to_waiting( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        # reset a task to the waiting state
        self.warning( "REMOTE: reset to waiting: " + task_id )
        if task_id == self.failout_id:
            print "resetting failout on " + self.failout_id + " prior to reset"
            os.environ['FAILOUT_ID'] = ""
        self.pool.reset_task( task_id )
        self.process_tasks = True
        return "Done"

    def reset_to_ready( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

       # reset a task to the ready state
        self.warning( "REMOTE: reset to ready: " + task_id )
        if task_id == self.failout_id:
            print "resetting failout on " + self.failout_id + " prior to reset"
            os.environ['FAILOUT_ID'] = ""
        self.pool.reset_task_to_ready( task_id )
        self.process_tasks = True
        return "Done"


    def reset_to_finished( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

      # reset a task to the waiting finished
        self.warning( "REMOTE: reset to finished: " + task_id )
        self.pool.reset_task_to_finished( task_id )
        self.process_tasks = True
        return "Done"


    def insert( self, ins, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        # insert a new task or task group into the system
        self.warning( "REMOTE: task insertion: " + ins )
        if ins == self.failout_id:
            # TO DO: DOES EQUALITY TEST FAIL IF INS IS A GROUP?
            print "resetting failout on " + self.failout_id + " prior to insertion"
            os.environ['FAILOUT_ID'] = ""
        self.pool.insertion( ins )
        self.process_tasks = True
        return "Done"


    def hold( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: system hold" )
        self.pool.set_system_hold()
        # process, to update state summary
        self.process_tasks = True
        return "Done"


    def resume( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: system resume" )
        self.pool.unset_system_hold()
        # process, to update state summary
        self.process_tasks = True
        return "Done"


    def set_stop_time( self, ctime, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: set stop time" )
        self.pool.set_stop_time( ctime )
        # process, to update state summary
        self.process_tasks = True
        return "Done"

    def set_hold_time( self, ctime, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: set hold time" )
        self.pool.set_system_hold( ctime )
        # process, to update state summary
        self.process_tasks = True
        return "Done"


    def shutdown( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: halt when running tasks finish" )
        self.hold( user )
        self.halt = True
        # process, to update state summary
        self.process_tasks = True
        return "Done"


    def shutdown_now( self, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: halt NOW" )
        self.hold( user )
        self.halt_now = True
        # process, to update state summary
        self.process_tasks = True
        return "Done"



    def get_config( self, item ):
        self.warning( "REMOTE: config item " + item )
        try:
            result = self.config.get( item )
        except:
            self.warning( "no such config item: " + item )
        else:
            return result

    def get_sys_info( self ):
        self.warning( "REMOTE: system info requested" )
        return [ self.config.get('system_title'), \
                self.config.get('system_def_dir'), \
                self.config.get('system_username'), \
                self.config.get('system_info') ]

    def get_task_info( self, task_names ):
        self.warning( "REMOTE: task info: " + ','.join(task_names ))
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
        self.warning( "REMOTE: requisite request")

        dump = {}
        found = False
        for task in self.tasks:
            id = task.id
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
            self.warning( 'No tasks found for the requisite dump request' )
 
        return dump
    
    def purge( self, task_id, stop, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: purge " + task_id + ' to ' + stop )
        self.pool.purge( task_id, stop )
        self.process_tasks = True
        return "Done"


    def die( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: die: " + task_id )
        self.pool.kill( [ task_id ] )
        self.process_tasks = True
        return "Done"

    def die_cycle( self, cycle, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: kill cycle: " + cycle )
        self.pool.kill_cycle( cycle )
        self.process_tasks = True
        return "Done"

    def spawn_and_die( self, task_id, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: spawn and die: " + task_id )
        self.pool.spawn_and_die( [ task_id ] )
        self.process_tasks = True
        return "Done"

    def spawn_and_die_cycle( self, cycle, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons

        self.warning( "REMOTE: spawn and die cycle: " + cycle )
        self.pool.spawn_and_die_cycle( cycle )
        self.process_tasks = True
        return "Done"

    def set_verbosity( self, level, user ):
        legal, reasons = self.is_legal( user )
        if not legal:
            return reasons


        if user != self.owner:
            return "ILLEGAL OPERATION: This system is owned by " + self.owner

        if self.locked:
            self.warning( "REMOTE: refusing verbosity request (locked)" )
            return "SORRY, THIS SYSTEM IS LOCKED"

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
            self.warning( "no such logging level: " + level )
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


    def should_i_die( self, task_id ):
        if self.halt:
            return True
