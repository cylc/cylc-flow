#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import copy
import sys, os
import Pyro.core
import logging
from TaskID import TaskID, TaskIDError
from CylcError import TaskNotFoundError, TaskStateError
from job_submission.job_submit import job_submit
from datetime import datetime
from version import cylc_version
from owner import user

class result:
    def __init__( self, success, reason="Action succeeded", value=None ):
        self.success = success
        self.reason = reason
        self.value = value

class remote_switch( Pyro.core.ObjBase ):
    "class to take remote suite control requests" 

    def __init__( self, config, clock, suite_dir, pool ):
        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)

        self.config = config
        self.clock = clock
        self.suite_dir = suite_dir
        self.insert_this = None

        self.pool = pool

        self.process_tasks = False
        self.halt = False
        self.halt_now = False

    def block( self ):
        if self.pool.blocked:
            return result( True, "(the suite is already blocked)" )
        self.pool.blocked = True
        self.process_tasks = True # to update monitor
        return result( True, "the suite has been blocked" )

    def unblock( self ):
        if not self.pool.blocked:
            return result( True, "(the suite is not blocked)" )
        self.pool.blocked = False
        self.process_tasks = True # to update monitor
        return result( True, "the suite has been unblocked" )

    def set_runahead( self, hours=None ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        # change the suite maximum runahead limit
        self.log.info( "setting runahead limit to " + str(hours) )
        if hours:
            self.pool.runahead_limit = int(hours)
        else:
            # No limit
            self.pool.runahead_limit = None

        self.process_tasks = True
        return result( True, "Action succeeded" )

    def nudge( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        # cause the task processing loop to be invoked
        self.log.info( "servicing suite nudge request" )
        # just set the "process tasks" indicator
        self.process_tasks = True
        return result( True )

    def ping_task( self, task_id ):
        # is this task running at the moment
        found = False
        running = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                found = True
                if itask.state.is_running():
                    running = True
                break
        if not found:
            return result( False, "Task not found: " + task_id )
        elif not running:
            return result( False, task_id + " is not currently running" )
        else:
            return result( True, task_id + " is currently running" )

    def trigger_task( self, task_id ):
        if self._suite_is_blocked():
            return result( False, "suite blocked" )
        try:
            self.pool.trigger_task( task_id )
        except TaskNotFoundError, x:
            self._warning( 'Refused remote trigger, task not found: ' + task_id )
            return result( False, x.__str__() )
        except Exception, x:
            # do not let a remote request bring the suite down for any reason
            self._warning( 'Remote reset failed: ' + x.__str__() )
            return result( False, "Action failed: "  + x.__str__() )
        else:
            # report success
            self.process_tasks = True
            return result( True )

    def reset_task_state( self, task_id, state ):
        if self._suite_is_blocked():
            return result( False, "suite blocked" )
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

    def add_prerequisite( self, task_id, message ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        try:
            self.pool.add_prerequisite( task_id, message )
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

    def insert( self, ins_id, stop_c_time=None ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        ins_name = self._name_from_id( ins_id )
        if not self._task_type_exists( ins_name ):
            # TASK INSERTION GROUPS TEMPORARILY DISABLED
            #and ins_name not in self.config[ 'task insertion groups' ]:
            #return result( False, "No such task or group: " + ins_name )
            return result( False, "there is no task " + ins_name + " in the suite graph." )
        ins = ins_id
        # insert a new task or task group into the suite
        try:
            inserted, rejected = self.pool.insertion( ins, stop_c_time )
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

        self.pool.hold_suite()
        # process, to update state summary
        self.process_tasks = True
        return result( True, "Tasks that are ready to run will not be submitted" )

    def resume( self ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        #if not self.pool.paused() and not self.pool.stopping():
        #    return result( True, "(the suite is not paused)" )
        self.pool.release_suite()
        # process, to update state summary
        self.process_tasks = True
        self.halt = False
        return result( True, "Tasks will be submitted when they are ready to run" )

    def set_stop( self, arg, method ):
        # first clear any existing stop times
        self.pool.clear_stop_times()
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        if method == 'stop after TAG':
            # ASSUME VALIDITY OF TAG TESTED ON INPUT
            self.pool.set_stop_ctime( arg )

        elif method == 'stop after clock time':
            try:
                date, time = arg.split('-')
                yyyy, mm, dd = date.split('/')
                HH,MM = time.split(':')
                dtime = datetime( int(yyyy), int(mm), int(dd), int(HH), int(MM) )
            except:
                return result( False, "Bad datetime (YYYY/MM/DD-HH:mm): " + arg )
            self.pool.set_stop_clock( dtime )

        elif method == 'stop after task':
            try:
                tid = TaskID( arg )
            except TaskIDError,x:
                return result( False, "Invalid stop task ID: " + arg )
            else:
                arg = tid.getstr()
            self.pool.set_stop_task( arg )

        # process, to update state summary
        self.process_tasks = True
        return result( True, "The suite will shutdown when requested: " + arg )

    def set_hold_time( self, ctime ):
        if self._suite_is_blocked():
            return result( False, "Suite Blocked" )
        self.pool.hold_suite( ctime )
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
        self.pool.hold_suite()
        self.halt_now = True
        # process, to update state summary
        self.process_tasks = True
        return result( True, "The suite will shut down immediately" )

    def get_cylc_version( self ):
        # for internal use (compat processing)
        return cylc_version

    def get_suite_info( self ):
        self.log.info( "servicing suite info request" )
        return [ self.config['title'], self.suite_dir, user ]

    def get_task_list( self, logit=True ):
        if logit:
            self.log.info( "servicing task list request" )
        return self.config.get_task_name_list()
 
    def get_task_info( self, task_names ):
        self.log.info( "servicing task info request" )
        info = {}
        for name in task_names:
            if self._task_type_exists( name ):
                info[ name ] = self.config.get_task_class( name ).describe()
            else:
                info[ name ] = ['ERROR: no such task type']
        return info

    def get_cycle_range( self ):
        return (self.config['scheduling']['initial cycle time'], self.config['scheduling']['final cycle time'] )

    def get_logging_directory( self ):
        return self.config['cylc']['logging']['directory']

    def get_family_nodes( self ):
        return self.config.members.keys()

    def get_graphed_family_nodes( self ):
        return self.config.families_used_in_graph

    def get_vis_families( self ):
        return self.config.vis_families

    def get_families( self ):
        return copy.deepcopy(self.config.members)

    def do_live_graph_movie( self ):
        return ( self.config['visualization']['enable live graph movie'],
                 self.config['visualization']['runtime graph']['directory'] ) 

    def get_family_hierarchy( self ):
        return copy.deepcopy(self.config.family_hierarchy)

    def get_graph_raw( self, cto, ctn, raw, group_nodes, ungroup_nodes,
            ungroup_recursive, group_all, ungroup_all ):
        return self.config.get_graph_raw( cto, ctn, raw, group_nodes,
                ungroup_nodes, ungroup_recursive, group_all, ungroup_all)

    def reconfigure( self ):
        self.log.info( "servicing suite reconfigure request")
        if self._suite_is_blocked():
            return result( False, "Suite is blocked" )
        try:
            self.pool.reconfigure()
        except Exception, x:
            return result( False, str(x) )
        else:
            return result( True, 'OK' )

    def get_task_requisites( self, in_ids ):
        self.log.info( "servicing task state info request")
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
        for task in self.pool.get_tasks():
            # loop through the suite task list
            task_id = task.id
            if task_id in in_ids_back:
                found = True
                extra_info = {}
                # extra info for clocktriggered tasks
                try:
                    extra_info[ 'Delayed start time reached' ] = task.start_time_reached() 
                    extra_info[ 'Triggers at' ] = 'T+' + str(task.real_time_delay) + ' hours'
                except AttributeError:
                    # not a clocktriggered task
                    pass
                # extra info for catchup_clocktriggered tasks
                try:
                    extra_info[ task.__class__.name + ' caught up' ] = task.__class__.get_class_var( 'caughtup' )
                except:
                    # not a catchup_clocktriggered task
                    pass
                # extra info for cycling tasks
                try:
                    extra_info[ 'Valid cycles' ] = task.valid_hours
                except AttributeError:
                    # not a cycling task
                    pass

                dump[ in_ids_back[ task_id ] ] = [ task.prerequisites.dump(), task.outputs.dump(), extra_info ]
        if not found:
            self._warning( 'task state info request: tasks not found' )
        else:
            return dump
    
    def purge( self, task_id, stop ):
        if self._suite_is_blocked():
            return result( False, "Suite is blocked" )

        if not self._task_type_exists( task_id ):
            return result( False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph." )

        self.log.info( "servicing purge request: " + task_id + ' to ' + stop )
        self.pool.purge( task_id, stop )
        self.process_tasks = True
        return result( True, "OK" )

    def die( self, task_id ):
        if self._suite_is_blocked():
            return result(False, "Suite is blocked")

        if not self._task_type_exists( task_id ):
            return result(False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph." )

        self.log.info( "servicing task removal request: " + task_id )
        self.pool.kill( [ task_id ] )
        self.process_tasks = True
        return result(True, "OK")

    def die_cycle( self, tag ):
        if self._suite_is_blocked():
            return result(False, "Suite is blocked")

        self.log.info( "servicing task removal request: " + tag )
        self.pool.kill_cycle( tag )
        self.process_tasks = True
        return result(True, "OK")

    def spawn_and_die( self, task_id ):
        if self._suite_is_blocked():
            return result(False, "Suite is blocked")

        if not self._task_type_exists( task_id ):
            return result(False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph." )

        self.log.info( "servicing task spawn and die request: " + task_id )
        self.pool.spawn_and_die( [ task_id ] )
        self.process_tasks = True
        return result(True, "OK")

    def spawn_and_die_cycle( self, tag ):
        if self._suite_is_blocked():
            return result(False, "Suite is blocked")
        self.log.info( "servicing task spawn and die request: " + tag )
        self.pool.spawn_and_die_cycle( tag )
        self.process_tasks = True
        return result(True, "OK")

    def set_verbosity( self, level ):
        if self._suite_is_blocked():
            return result(False, "Suite is blocked")

        # change the verbosity of all the logs:
        #   debug, info, warning, error, critical
        self.log.info( "servicing suite verbosity change request " + level )
        
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
            return result( False, "Illegal logging level: " + level)

        self.log.setLevel( new_level )
        return result(True, 'OK')

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
        if self.pool.blocked:
            self._warning( "Refusing remote request (suite blocked)" )
            return True
        else:
            return False

    def _name_from_id( self, task_id ):
        if '%' in task_id:
            name, tag = task_id.split('%')
        else:
            name = task_id
        return name

    def _warning( self, msg ):
        print
        self.log.warning( msg )

    def get_live_graph( self ):
        lg = self.pool.get_live_graph()
        if lg:
            return lg
        else:
            return None

    def hold_task( self, task_id ):
        if self._suite_is_blocked():
            return result( False, "Suite is blocked" )

        if not self._task_type_exists( task_id ):
            return result(  False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph."  )

        self.log.info( "servicing task hold request: " + task_id )
        found = False
        was_waiting = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                found = True
                print itask.state.state['status']
                if itask.state.is_waiting() or itask.state.is_queued():
                    was_waiting = True
                    itask.state.set_status( 'held' )
                break
        if found:
            if was_waiting:
                self.process_tasks = True # to update monitor
                return result( True, "OK" )
            else:
                return result( False, "Task was not waiting or queued" )
        else:
            return result( False, "Task not found" )

    def release_task( self, task_id ):
        if self._suite_is_blocked():
            return result( False, "Suite is blocked" )

        if not self._task_type_exists( task_id ):
            return result( False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph."  )

        self.log.info( "servicing task release request: " + task_id )
        found = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                itask.state.set_status( 'waiting' )
                found = True
                break
        if found:
            self.process_tasks = True # to update monitor
            return result( True, "OK" )
        else:
            return result( False, "Task not found" )


