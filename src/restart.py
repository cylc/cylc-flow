#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from task_pool import task_pool
import sys, os, re
from dynamic_instantiation import get_object

class restart( task_pool ):

    def __init__( self, config, pyro, dummy_mode, use_quick,
            logging_dir, logging_level, state_dump_file, exclude, include,
            initial_state_dump, no_reset, stop_time, pause_time, graphfile ):

        self.initial_state_dump = initial_state_dump
        self.no_reset = no_reset

        task_pool.__init__( self, config, pyro, dummy_mode, use_quick,
                logging_dir, logging_level, state_dump_file, exclude, include,
                stop_time, pause_time, graphfile )

    def load_tasks( self ):
        # load initial suite state from the configured state dump file
        #--

        filename = self.initial_state_dump
        no_reset = self.no_reset
        excluded_by_commandline = self.exclude
        included_by_commandline = self.include

        print '\nLOADING INITIAL STATE FROM ' + filename + '\n'
        self.log.info( 'Loading initial state from ' + filename )

        included_by_rc = self.config.get( 'included_tasks' )
        excluded_by_rc = self.config.get( 'excluded_tasks' )

        include_list_supplied = False
        if len( included_by_commandline ) > 0 or len( included_by_rc ) > 0:
            include_list_supplied = True
            included_tasks = included_by_commandline + included_by_rc

        # The state dump file format is:
        # suite time : <time>
        #   OR
        # dummy time : <time>,rate
        #   THEN
        # class <classname>: item1=value1, item2=value2, ... 
        # <task_id> : <state>
        # <task_id> : <state>
        #   ...
        # The time format is defined by the clock.reset()
        # task <state> format is defined by task_state.dump()

        FILE = open( filename, 'r' )
        lines = FILE.readlines()
        FILE.close()

        # RESET THE TIME TO THE LATEST DUMPED TIME
        # The state dump file first line is:
        # suite time : <time>
        #   OR
        # dummy time : <time>,rate
        line1 = lines[0]
        line1 = line1.rstrip()
        [ time_type, time_string ] = line1.split(' : ')
        if time_type == 'dummy time':
            if not self.dummy_mode:
                raise SystemExit("You can't restart in real mode from a dummy mode state dump")
            
            [ time, rate ] = time_string.split( ',' )
            self.clock.reset( time, rate )

        mod = __import__( 'task_classes' )

        # parse each line and create the task it represents
        for line in lines[1:]:
            # strip trailing newlines
            line = line.rstrip( '\n' )

            if re.match( '^class', line ):
                # class variables
                [ left, right ] = line.split( ' : ' )
                [ junk, classname ] = left.split( ' ' ) 
                cls = getattr( mod, classname )
                pairs = right.split( ', ' )
                for pair in pairs:
                    [ item, value ] = pair.split( '=' )
                    cls.set_class_var( item, value )
                 
                continue

            # instance variables
            ( id, state ) = line.split(' : ')
            ( name, c_time ) = id.split('%')

            if name in excluded_by_commandline or name in excluded_by_rc:
                continue

            if include_list_supplied:
                if name not in included_tasks:
                    continue

            itask = get_object( 'task_classes', name )\
                    ( c_time, state, startup=False )

            if itask.state.is_finished():  
                # must have satisfied prerequisites and completed outputs
                itask.log( 'NORMAL', "starting in FINISHED state" )
                itask.prerequisites.set_all_satisfied()
                itask.outputs.set_all_complete()

            elif itask.state.is_submitted() or itask.state.is_running():  
                # Must have satisfied prerequisites. These tasks may have
                # finished after the suite was shut down, but as we
                # can't know that for sure we have to re-submit them.
                itask.log( 'NORMAL', "starting in READY state" )
                itask.state.set_status( 'waiting' )
                itask.prerequisites.set_all_satisfied()

            elif itask.state.is_failed():
                # Re-submit these unless the suite operator says not to. 
                if no_reset:
                    itask.log( 'WARNING', "starting in FAILED state: manual reset required" )
                    itask.prerequisites.set_all_satisfied()
                else:
                    itask.log( 'NORMAL', "starting in READY state" )
                    itask.state.set_status( 'waiting' )
                    itask.prerequisites.set_all_satisfied()

            # check stop time in case the user has set a very quick stop
            if self.stop_time and int( itask.c_time ) > int( self.stop_time ):
                # we've reached the stop time already: delete the new task 
                itask.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                itask.prepare_for_death()
                del itask
 
            else:
                self.insert( itask )
