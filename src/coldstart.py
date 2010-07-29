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
            start_time, stop_time, pause_time ):

        self.start_time = start_time

        task_pool.__init__( self, config, pyro, dummy_mode, use_quick,
                logging_dir, logging_level, state_dump_file, exclude, include,
                stop_time, pause_time )

    def load_tasks( self ):
        # load initial suite state from configured tasks and start time
        #--
        
        start_time = self.start_time
        exclude = self.exclude
        include = self.include

        # set clock before using log (affects dummy mode only)
        self.clock.set( start_time )

        #print '\nSTARTING AT ' + start_time + ' FROM CONFIGURED TASK LIST\n'
        self.log.info( 'Loading state from configured task list' )
        # config.task_list = [ taskname1, taskname2, ...]

        task_list = self.config.get('task_list')
        # uniquify in case of accidental duplicates
        task_list = list( set( task_list ) )

        for name in task_list:

            if name in exclude:
                continue

            if len( include ) > 0:
                if name not in include:
                    continue
            
            # create the task-specific logger
            self.create_task_log( name )

            itask = get_object( 'task_classes', name )\
                    ( start_time, 'waiting', startup=True )

            # check stop time in case the user has set a very quick stop
            if self.stop_time and int( itask.c_time ) > int( self.stop_time ):
                # we've reached the stop time already: delete the new task 
                itask.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                itask.prepare_for_death()
                del itask
 
            else:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.id )
                self.tasks.append( itask )
