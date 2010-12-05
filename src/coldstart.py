#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from dynamic_instantiation import get_object
from task_pool import task_pool

class coldstart( task_pool ):
    def __init__( self, config, pyro, dummy_mode, use_quick,
            logging_dir, logging_level, state_dump_file, exclude, include,
            start_time, stop_time, pause_time, warm_start, graphfile ):

        self.start_time = start_time
        self.warm_start = warm_start

        task_pool.__init__( self, config, pyro, dummy_mode, use_quick,
                logging_dir, logging_level, state_dump_file, exclude, include,
                stop_time, pause_time, graphfile )

    def load_tasks( self ):
        # load initial suite state from configured tasks and start time
        #--
        
        start_time = self.start_time
        excluded_by_commandline = self.exclude
        included_by_commandline = self.include

        # set clock before using log (affects dummy mode only)
        self.clock.set( start_time )

        #print '\nSTARTING AT ' + start_time + ' FROM CONFIGURED TASK LIST\n'
        self.log.info( 'Loading state from configured task list' )
        # config.task_list = [ taskname1, taskname2, ...]

        task_list = self.config.get('task_list')

        # uniquify in case of accidental duplicates (Python 2.4+)
        task_list = list( set( task_list ) )

        coldstart_tasks = self.config.get( 'coldstart_tasks' )
        included_by_rc = self.config.get( 'included_tasks' )
        excluded_by_rc = self.config.get( 'excluded_tasks' )

        include_list_supplied = False
        if len( included_by_commandline ) > 0 or len( included_by_rc ) > 0:
            include_list_supplied = True
            included_tasks = included_by_commandline + included_by_rc

        for name in task_list:
            if name in excluded_by_commandline or name in excluded_by_rc:
                continue

            if include_list_supplied:
                if name not in included_tasks:
                    continue
            
            itask = get_object( 'task_classes', name )\
                    ( start_time, 'waiting', startup=True )

            if self.warm_start and name in coldstart_tasks:
                itask.log( 'WARNING', "warm start: starting in finished state" )
                itask.state.set_status( 'finished' )
                itask.prerequisites.set_all_satisfied()
                itask.outputs.set_all_complete()

            # check stop time in case the user has set a very quick stop
            if self.stop_time and int( itask.c_time ) > int( self.stop_time ):
                # we've reached the stop time already: delete the new task 
                itask.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                itask.prepare_for_death()
                del itask
 
            else:
                self.insert( itask )
