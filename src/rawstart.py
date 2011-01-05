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

class rawstart( task_pool ):
    def __init__( self, config, clock, pyro, dummy_mode, use_quick,
            logging_dir, logging_level, state_dump_file, exclude, include,
            start_time, stop_time, pause_time, graphfile ):

        self.start_time = start_time

        task_pool.__init__( self, config, clock, pyro, dummy_mode, use_quick,
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

        task_list = self.config.get_task_name_list()

        # uniquify in case of accidental duplicates (Python 2.4+)
        task_list = list( set( task_list ) )

        coldstart_tasks = self.config[ 'coldstart task list' ]
        included_by_rc  = self.config[ 'include task list'   ]
        excluded_by_rc  = self.config[ 'exclude task list'   ]

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
            
            itask = self.config.get_task_proxy( name, start_time, 'waiting', startup=True )

            if name in coldstart_tasks:
                itask.log( 'WARNING', "This is a raw start: I will self-destruct." )
                itask.prepare_for_death()
                del itask
                continue
 
            # check stop time in case the user has set a very quick stop
            if self.stop_time and int( itask.c_time ) > int( self.stop_time ):
                # we've reached the stop time already: delete the new task 
                itask.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                itask.prepare_for_death()
                del itask
                continue
 
            self.insert( itask )
