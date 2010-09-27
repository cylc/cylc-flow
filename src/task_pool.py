#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import datetime
import cycle_time
import pimp_my_logger
import logging
import sys, os, re
from dynamic_instantiation import get_object
from broker import broker
from Pyro.errors import NamingError, ProtocolError

class task_pool:
    def __init__( self, config, pyro, dummy_mode, use_quick,
            logging_dir, logging_level, state_dump_file, exclude,
            include, stop_time, pause_time, graphfile ):

        self.config = config
        self.use_quick = use_quick
        self.pyro = pyro
        self.dummy_mode = dummy_mode
        self.logging_dir = logging_dir
        self.logging_level = logging_level
        self.state_dump_file = state_dump_file
        self.exclude = exclude
        self.include = include
        self.stop_time = stop_time
        self.suite_hold_ctime = pause_time
        self.suite_hold_now = False

        # TO DO: use self.config.get('foo') throughout
        self.clock = config.get('clock')

        # initialise the dependency broker
        self.broker = broker()

        self.tasks = []

        # create main logger
        self.create_main_log()

        # set job submit method for each task class
        jsc = config.get( 'job submit class' )
        clsmod = __import__( 'task_classes' )
        for name in jsc:
            cls = getattr( clsmod, name )
            setattr( cls, 'job_submit_method', jsc[ name ] )
            
        # instantiate the initial task list and create loggers 
        # PROVIDE THIS METHOD IN DERIVED CLASSES
        self.load_tasks()

        # configure graph file parameters
        self.graphfile = graphfile
        if graphfile:
            self.node_color = {}
            self.node_shape = {}
            self.edge_color = {}
            for task in self.config.get( 'task_list' ):
                node_colors = self.config.get( 'node_colors' )
                node_shapes = self.config.get( 'node_shapes' )
                if task in node_colors:
                    self.node_color[ task ] = node_colors[ task ]
                    if self.config.get( 'use_node_color_for_edges' ):
                        self.edge_color[ task ] = node_colors[ task ]
                if task in node_shapes:
                    self.node_shape[ task ] = node_shapes[ task ]

        # determine task families and family members
        # (used in writing out the 'dot' graph file).
        self.members = {}
        self.middle_member = {}
        self.member_of = {}
        for name in self.config.get('task_list'):
            mod = __import__( 'task_classes' )
            cls = getattr( mod, name )
            try:
                mems = getattr( cls, 'members' ) 
            except AttributeError:
                pass
            else:
                self.members[ name ] = mems
                mems.sort()
                self.middle_member[ name ] = mems[ len( mems ) / 2  ]

            try:
                memof = getattr( cls, 'member_of' )
            except AttributeError:
                pass
            else:
                self.member_of[ name ] = memof
 

    def create_main_log( self ):
        log = logging.getLogger( 'main' )
        pimp_my_logger.pimp_it( \
             log, 'main', self.logging_dir, \
                self.logging_level, self.dummy_mode, self.clock )
        # log to the main log
        self.log = log

    def create_task_log( self, name ):
        log = logging.getLogger( 'main.' + name )
        pimp_my_logger.pimp_it( \
             log, name, self.logging_dir, \
                self.logging_level, self.dummy_mode, self.clock )

    def get_tasks( self ):
        return self.tasks

    def set_stop_time( self, stop_time ):
        self.log.debug( "Setting stop time: " + stop_time )
        self.stop_time = stop_time

    def set_suite_hold( self, ctime = None ):
        self.log.warning( 'pre-hold state dump: ' + self.dump_state( new_file = True ))
        if ctime:
            self.suite_hold_ctime = ctime
            self.log.critical( "HOLD: no new tasks will run from " + ctime )
        else:
            self.suite_hold_now = True
            self.log.critical( "HOLD: no more tasks will run")

    def unset_suite_hold( self ):
        self.log.critical( "UNHOLD: new tasks will run when ready")
        self.suite_hold_now = False
        self.suite_hold_ctime = None

    def will_stop_at( self ):
        return self.stop_time

    def paused( self ):
        return self.suite_hold_now

    def will_pause_at( self ):
        return self.suite_hold_ctime

    def get_oldest_c_time( self ):
        # return the cycle time of the oldest task
        oldest = 9999887766
        for itask in self.tasks:
            #if itask.state.is_failed():  # uncomment for earliest NON-FAILED 
            #    continue

            # avoid daemon tasks
            if hasattr( itask, 'daemon_task' ):
                continue

            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def no_tasks_running( self ):
        # return True if no tasks are submitted or running
        #--
        for itask in self.tasks:
            if itask.state.is_running() or itask.state.is_submitted():
                return False
        return True

    def all_tasks_finished( self ):
        # return True if all tasks have finished AND spawned
        #--
        for itask in self.tasks:
            if not itask.state.is_finished() or not itask.state.has_spawned():
                return False
        return True


    def negotiate( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.
        #--

        self.broker.reset()

        for itask in self.tasks:
            # register task outputs
            self.broker.register( itask )

        for itask in self.tasks:
            # try to satisfy me (itask) if I'm not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        for itask in self.tasks:
            itask.check_requisites()

    def set_node( self, node_id ):

        if node_id in self.node_seen:
            return

        self.node_seen[ node_id ] = True
        name, ctime = node_id.split( '%' )
        node = name + '_' + ctime
 
        col = False
        shp = False
        if name in self.node_color:
            col = True
            colstr = 'fillcolor=' + self.node_color[ name ] 
        if name in self.node_shape:
            shp = True
            shpstr = 'shape=' + self.node_shape[ name ]

        if col and shp:
            self.graphfile.write( node + ' [ ' + colstr + ', ' + shpstr + ' ];\n' )
        elif col:
            self.graphfile.write( node + ' [ ' + colstr + ' ];\n' )
        elif shp:
            self.graphfile.write( node + ' [ ' + shpstr + ' ];\n' )


    def set_graph( self, source_id, target_id=None, edge_spec=None ):

            name, ctime = source_id.split( '%' )
            # dot files do not like percent characters
            source = name + '_' + ctime
            self.set_node( source_id )

            if target_id:
                target = re.sub( '%', '_', target_id )
                self.set_node( target_id )

                if name in self.edge_color:
                    if edge_spec:
                        self.graphfile.write( '    ' + source + ' -> ' + target + ' [' + edge_spec + ', color=' + self.edge_color[name] + '];\n' )
                    else:
                        self.graphfile.write( '    ' + source + ' -> ' + target + ' [color=' + self.edge_color[name] + '];\n' )
                else:
                    if edge_spec:
                        self.graphfile.write( '    ' + source + ' -> ' + target + ' [' + edge_spec + '];\n' )
                    else:
                        self.graphfile.write( '    ' + source + ' -> ' + target + ';\n' )

            else:
                # family member
                self.graphfile.write( '        ' + source + ';\n' )

    def run_tasks( self ):
        # tell each task to run if it is ready
        # unless the suite is on hold
        #--
        if self.suite_hold_now:
            # general suite hold
            self.log.debug( 'not asking any tasks to run (general suite hold in place)' )
            return

        for itask in self.tasks:
                if self.suite_hold_ctime:
                    if int( itask.c_time ) > int( self.suite_hold_ctime ):
                        self.log.debug( 'not asking ' + itask.id + ' to run (' + self.suite_hold_ctime + ' hold in place)' )
                        continue

                current_time = self.clock.get_datetime()
                if itask.run_if_ready( current_time ):

                    if self.graphfile:
                        self.node_seen = {}

                        target_id = itask.id 
                        if not self.config.get( 'task_families_in_subgraphs' ):
                            for source_id in itask.get_resolved_dependencies():
                                self.set_graph( source_id, target_id )
                            continue

                        # GRAPH TASK FAMILIES IN AN INTUITIVE WAY (boxed subgraph):

                        # ASSUME a task family and its members are cotemporal
                        target_name = itask.name
                        ctime = itask.c_time
                        target = target_name + '_' + ctime

                        if target_name in self.members:
                            # TARGET IS A TASK FAMILY
                            # replace target with a boxed subgraph of
                            # family members with no internal edges.
                            members = self.members[ target_name ]
                            # define the subgraph ...
                            self.graphfile.write( '    subgraph cluster_' + target + ' {\n' )
                            self.graphfile.write( '        //graph [ color=midnightblue];\n' )
                            self.graphfile.write( '        //node [ fillcolor=paleturquoise ];\n' )
                            self.graphfile.write( '        label = "' + target_name + ' task family";\n' )

                            for member in members:
                                # write family members with no edges
                                member_id = member + '%' + ctime
                                self.set_graph( member_id )

                            # close subgraph
                            self.graphfile.write( '    };\n' )

                            # ... and replace target with an edge to the middle family member
                            repl_target_id = self.middle_member[target_name] + '%' + ctime

                            for source_id in itask.get_resolved_dependencies():
                                self.set_graph( source_id, repl_target_id, 'lhead=cluster_' + target )

                        elif target_name in self.member_of:
                            # TARGET IS A FAMILY MEMBER
                            for source_id in itask.get_resolved_dependencies():

                                (source_name, source_ctime ) = source_id.split('%')

                                if source_name in self.members:
                                    # target is a member, source is a family
                                    pass
                                else:
                                    # target is a member, source is not a family, 
                                    self.set_graph( source_id, target_id )

                        else:
                            # TARGET IS NOT A FAMILY OR A FAMILY MEMBER
                            for source_id in itask.get_resolved_dependencies():

                                source_name, source_ctime = source_id.split('%')
                                source = source_name + '_' + source_ctime

                                if source_name in self.members:
                                    # SOURCE IS A FAMILY, REPLACE WITH MIDDLE MEMBER
                                    repl_source_id = self.middle_member[source_name] + '%' + source_ctime
                                    self.set_graph( repl_source_id, target_id, 'ltail=cluster_' + source )
                                else:
                                    self.set_graph( source_id, target_id )

    def spawn( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) spawns
        #--

        # update oldest suite cycle time
        oldest_c_time = self.get_oldest_c_time()

        for itask in self.tasks:

            tdiff = cycle_time.decrement( itask.c_time, int( self.config.get('max_runahead_hours')))
            if int( tdiff ) > int( oldest_c_time ):
                # too far ahead: don't spawn this task.
                itask.log( 'DEBUG', "delaying spawning (too far ahead)" )
                continue

            if itask.ready_to_spawn():
                itask.log( 'DEBUG', 'spawning')

                # dynamic task object creation by task and module name
                new_task = itask.spawn( 'waiting' )
                if self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.insert( new_task )


    def force_spawn( self, itask ):
        if itask.state.has_spawned():
            return None
        else:
            itask.state.set_spawned()
            itask.log( 'DEBUG', 'forced spawning')
            # dynamic task object creation by task and module name
            new_task = itask.spawn( 'waiting' )
            if self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
                # we've reached the stop time: delete the new task 
                new_task.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                new_task.prepare_for_death()
                del new_task
            else:
                # no stop time, or we haven't reached it yet.
                self.insert( new_task )
            return new_task

    def dump_state( self, new_file = False ):
        filename = self.state_dump_file 
        if new_file:
            filename += '.' + self.clock.dump_to_str()

        # suite time
        FILE = open( filename, 'w' )
        if self.dummy_mode:
            FILE.write( 'dummy time : ' + self.clock.dump_to_str() + ',' + str( self.clock.get_rate()) + '\n' )
        else:
            FILE.write( 'suite time : ' + self.clock.dump_to_str() + '\n' )

        # task class variables
        for name in self.config.get('task_list'):
            mod = __import__( 'task_classes' )
            cls = getattr( mod, name )
            cls.dump_class_vars( FILE )
            
        # task instance variables
        for itask in self.tasks:
            itask.dump_state( FILE )
        FILE.close()
        # return the filename (minus path)
        return os.path.basename( filename )

    def earliest_unspawned( self ):
        all_spawned = True
        earliest_unspawned = None
        for itask in self.tasks:
            if not itask.state.has_spawned():
                all_spawned = False
                if not earliest_unspawned:
                    earliest_unspawned = itask.c_time
                elif int( itask.c_time ) < int( earliest_unspawned ):
                    earliest_unspawned = itask.c_time

        return [ all_spawned, earliest_unspawned ]

    def earliest_unsatisfied( self ):
        # find the earliest unsatisfied task
        all_satisfied = True
        earliest_unsatisfied = None
        for itask in self.tasks:
            if not itask.prerequisites.all_satisfied():
                all_satisfied = False
                if not earliest_unsatisfied:
                    earliest_unsatisfied = itask.c_time
                elif int( itask.c_time ) < int( earliest_unsatisfied ):
                    earliest_unsatisfied = itask.c_time

        return [ all_satisfied, earliest_unsatisfied ]

    def earliest_unfinished( self ):
        # find the earliest unfinished task
        all_finished = True
        earliest_unfinished = None
        for itask in self.tasks:
            #if itask.state.is_failed():  # uncomment for earliest NON-FAILED
            #    continue

            # avoid daemon tasks
            if hasattr( itask, 'daemon_task' ):
                continue

            if not itask.state.is_finished():
                all_finished = False
                if not earliest_unfinished:
                    earliest_unfinished = itask.c_time
                elif int( itask.c_time ) < int( earliest_unfinished ):
                    earliest_unfinished = itask.c_time

        return [ all_finished, earliest_unfinished ]

    def cleanup( self ):
        # Delete tasks that are no longer needed, i.e. those that
        # spawned, finished, AND are no longer needed to satisfy
        # the prerequisites of other tasks.
        #--

        # times of any failed tasks. 
        failed_rt = {}
        for itask in self.tasks:
            if itask.state.is_failed():
                failed_rt[ itask.c_time ] = True

        # suicide
        for itask in self.tasks:
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    self.spawn_and_die( [itask.id], dump_state=False, reason='death by suicide' )

        #### RESTORE FOR TESTING ASYNCHRONOUS TASK FUNCTIONALITY:
        #### self.cleanup_async()

        if self.use_quick:
            self.cleanup_non_intercycle( failed_rt )

        self.cleanup_generic( failed_rt )

    def cleanup_async( self ):
        spent = []
        for itask in self.tasks:
            if not itask.done():
                continue
            try:
                itask.death_prerequisites
            except AttributeError:
                pass
            else:
                if itask.death_prerequisites.all_satisfied():
                    print "ASYNC SPENT", itask.id
                    spent.append( itask )

        # delete the spent tasks
        for itask in spent:
            self.trash( itask, 'quick death' )

    def cleanup_non_intercycle( self, failed_rt ):
        # A/ Non INTERCYCLE tasks by definition have ONLY COTEMPORAL
        # DOWNSTREAM DEPENDANTS). i.e. they are no longer needed once
        # their cotemporal peers have finished AND there are no
        # unspawned tasks with earlier cycle times. So:
        #
        # (i) FREE TASKS are spent if they are:
        #    spawned, finished, no earlier unspawned tasks.
        #
        # (ii) TIED TASKS are spent if they are:
        #    spawned, finished, no earlier unspawned tasks, AND there is
        #    at least one subsequent instance that is FINISHED
        #    ('satisfied' would do but that allows elimination of a tied
        #    task whose successor could subsequently fail, thus
        #    requiring manual task reset after a restart).
        #  ALTERNATIVE TO (ii): DO NOT ALLOW non-INTERCYCLE tied tasks
        #--

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        # find the spent quick death tasks
        spent = []
        for itask in self.tasks:
            if itask.intercycle: 
                # task not up for consideration here
                continue
            if not itask.has_spawned():
                # task has not spawned yet, or will never spawn (oneoff tasks)
                continue
            if not itask.done():
                # task has not finished yet
                continue

            #if itask.c_time in failed_rt.keys():
            #    # task is cotemporal with a failed task
            #    # THIS IS NOT NECESSARY AS WE RESTART FAILED
            #    # TASKS IN THE READY STATE?
            #    continue

            if all_spawned:
                # (happens prior to shutting down at stop top time)
                # (=> earliest_unspawned is undefined)
                continue

            if int( itask.c_time ) >= int( earliest_unspawned ):
                # An EARLIER unspawned task may still spawn a successor
                # that may need me to satisfy its prerequisites.
                # The '=' here catches cotemporal unsatisfied tasks
                # (because an unsatisfied task cannot have spawned).
                continue

            if hasattr( itask, 'is_tied' ):
                # Is there a later finished instance of the same task?
                # It must be FINISHED in case the current task fails and
                # cannot be fixed => the task's manually inserted
                # post-gap successor will need to be satisfied by said
                # finished task. 
                there_is = False
                for t in self.tasks:
                    if t.name == itask.name and \
                            int( t.c_time ) > int( itask.c_time ) and \
                            t.state.is_finished():
                                there_is = True
                                break
                if not there_is:
                    continue

            # and, by a process of elimination
            spent.append( itask )
 
        # delete the spent quick death tasks
        for itask in spent:
            self.trash( itask, 'quick death' )

    def cleanup_generic( self, failed_rt ):
        # B/ THE GENERAL CASE
        # No finished-and-spawned task that is later than the earliest
        # unsatisfied task can be deleted yet because it may still be
        # needed to satisfy new tasks that may appear when earlier (but
        # currently unsatisfied) tasks spawn. Therefore only
        # finished-and-spawned tasks that are earlier than the
        # earliest unsatisfied task are candidates for deletion. Of
        # these, we can delete a task only IF another spent instance of
        # it exists at a later time (but still earlier than the earliest
        # unsatisfied task) 

        # BUT while the above paragraph is correct, the method can fail
        # at restart: just before shutdown, when all running tasks have
        # finished, we briefly have 'all tasks satisfied', which allows 
        # deletion without the 'earliest unsatisfied' limit, and can
        # result in deletion of finished tasks that are still required
        # to satisfy others after a restart.

        # THEREFORE the correct deletion cutoff is 'EARLIEST UNFINISHED'
        # (members of which will remain in, or be reset to, the waiting
        # state on a restart. The only way to use 'earliest unsatisfied'
        # over a restart would be to record the state of all
        # prerequisites for each task in the state dump (which may be a
        # good thing to do?)

        [ all_finished, earliest_unfinished ] = self.earliest_unfinished()
        if all_finished:
            self.log.debug( "all tasks finished" )
        else:
            self.log.debug( "earliest unfinished: " + earliest_unfinished )

         # find candidates for deletion
        candidates = {}
        for itask in self.tasks:

            if not itask.done():
                continue

            if itask.c_time in failed_rt.keys():
                continue

            #if not all_satisfied:
            #    if int( itask.c_time ) >= int( earliest_unsatisfied ):
            #        continue
            if not all_finished:
                if int( itask.c_time ) >= int( earliest_unfinished ):
                    continue
            
            if itask.c_time in candidates.keys():
                candidates[ itask.c_time ].append( itask )
            else:
                candidates[ itask.c_time ] = [ itask ]

        # searching from newest tasks to oldest, after the earliest
        # unsatisfied task, find any done task types that appear more
        # than once - the second or later occurrences can be deleted.
        ctimes = candidates.keys()
        ctimes.sort( key = int, reverse = True )
        seen = {}
        spent = []
        for rt in ctimes:
            #if not all_satisfied:
            #    if int( rt ) >= int( earliest_unsatisfied ):
            #        continue
            if not all_finished:
                if int( rt ) >= int( earliest_unfinished ):
                    continue
            
            for itask in candidates[ rt ]:
                if hasattr( itask, 'is_oneoff' ):
                    # oneoff candidates that do not nominate a follow-on can
                    # be assumed to have no non-cotemporal dependants
                    # and can thus be eliminated.
                    try:
                        name = itask.oneoff_follow_on
                    except AttributeError:
                        spent.append( itask )
                        continue
                else:
                    name = itask.name

                if name in seen.keys():
                    # already seen this guy, so he's spent
                    spent.append( itask )
                    
                else:
                    # first occurence
                    seen[ name ] = True
            
        # now delete the spent tasks
        for itask in spent:
            self.trash( itask, 'general' )


    def reset_task( self, task_id ):
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))
        found = False
        for itask in self.tasks:
            if itask.id == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to waiting state" )
            itask.state.set_status( 'waiting' )
            itask.prerequisites.set_all_unsatisfied()
            itask.outputs.set_all_incomplete()
            try:
                # remove the tasks's "failed" output
                itask.outputs.remove( task_id + ' failed' )
            except:
                # task had no "failed" output
                pass
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def reset_task_to_ready( self, task_id ):
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))
        found = False
        for itask in self.tasks:
            if itask.id == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to ready state" )
            itask.state.set_status( 'waiting' )
            itask.prerequisites.set_all_satisfied()
            itask.outputs.set_all_incomplete()
            try:
                # remove the tasks's "failed" output
                itask.outputs.remove( task_id + ' failed' )
            except:
                # task had no "failed" output
                pass
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def reset_task_to_finished( self, task_id ):
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))
        found = False
        for itask in self.tasks:
            if itask.id == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to finished state" )
            itask.state.set_status( 'finished' )
            itask.prerequisites.set_all_satisfied()
            itask.outputs.set_all_complete()
            try:
                # remove the tasks's "failed" output
                itask.outputs.remove( task_id + ' failed' )
            except:
                # task had no "failed" output
                pass
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def insertion( self, ins_id ):
        # for remote insertion of a new task, or task group
        self.log.warning( 'pre-insertion state dump: ' + self.dump_state( new_file = True ))
        try:
            ( ins_name, ins_ctime ) = ins_id.split( '%' )
            print
            if ins_name in self.config.get( 'task_list' ):
                print "INSERTING A TASK"
                ids = [ ins_id ]
            elif ins_name in ( self.config.get( 'task_groups' ) ).keys():
                print "INSERTING A GROUP OF TASKS"
                tasknames = self.config.get( 'task_groups')[ins_name]
                ids = []
                for name in tasknames:
                    ids.append( name + '%' + ins_ctime )
            else:
                # THIS WILL BE CAUGHT BY THE TRY BLOCK
                raise SystemExit("no such task or group")

            for task_id in ids:
                [ name, c_time ] = task_id.split( '%' )
                # instantiate the task proxy
                itask = get_object( 'task_classes', name )\
                        ( c_time, 'waiting', startup=False )
                if itask.instance_count == 1:
                    # first task of its type, so create the log
                    log = logging.getLogger( 'main.' + name )
                    pimp_my_logger.pimp_it( log, name, self.logging_dir, \
                            self.logging_level, self.dummy_mode, self.clock )
                # the initial task cycle time can be altered during
                # creation, so we have to create the task before
                # checking if stop time has been reached.
                skip = False
                if self.stop_time:
                    if int( itask.c_time ) > int( self.stop_time ):
                        itask.log( 'WARNING', " STOPPING at " + self.stop_time )
                        itask.prepare_for_death()
                        del itask
                        skip = True
                if not skip:
                    self.insert( itask )

        #except NamingError, e:
        except Exception, e:
            # A failed remote insertion should not bring the suite down
            # under any circumstances (e.g. requests to insert undefined
            # tasks).
            print 'INSERTION FAILED:', e
            print 

    def purge( self, id, stop ):
        # Remove an entire dependancy tree rooted on the target task,
        # through to the given stop time (inclusive). In general this
        # involves tasks that do not even exist yet within the pool.

        # Method: trigger the target task *virtually* (i.e. without
        # running the real task) by: setting it to the finished state,
        # setting all of its outputs completed, and forcing it to spawn.
        # (this is equivalent to instantaneous successful completion as
        # far as cylc is concerned). Then enter the normal dependency
        # negotation process to trace the downstream effects of this,
        # also triggering subsequent tasks virtually. Each time a task
        # triggers mark it as a dependency of the target task for later
        # deletion (but not immmediate deletion because other downstream
        # tasks may still trigger off its outputs).  Downstream tasks
        # (freshly spawned or not) are not triggered if they have passed
        # the stop time, and the process is stopped is soon as a
        # dependency negotation round results in no new tasks
        # triggering.

        # Finally, reset the prerequisites of all tasks spawned during
        # the purge to unsatisfied, since they may have been satisfied
        # by the purged tasks in the "virtual" dependency negotiations.
        # TO DO: THINK ABOUT WHETHER THIS CAN APPLY TO TASKS THAT
        # ALREADY EXISTED PRE-PURGE, NOT ONLY THE JUST-SPAWNED ONES. If
        # so we should explicitly record the tasks that get satisfied
        # during the purge.

        self.log.warning( 'pre-purge state dump: ' + self.dump_state(
            new_file = True ))

        die = []
        spawn = []

        for itask in self.tasks:
            # Find the target task
            if itask.id == id:
                # set it finished
                itask.set_finished()
                # force it to spawn
                foo = self.force_spawn( itask )
                if foo:
                    spawn.append( foo )
                # mark it for later removal
                die.append( id )
                break

        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.negotiate()
            something_triggered = False
            for itask in self.tasks:
                current_time = self.clock.get_datetime()
                if itask.ready_to_run( current_time ) and int( itask.c_time ) <= int( stop ):
                    something_triggered = True
                    itask.set_finished()
                    foo = self.force_spawn( itask )
                    if foo:
                        spawn.append( foo )
                    die.append( itask.id )
 
        # reset any prerequisites "virtually" satisfied during the purge
        for task in spawn:
            task.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        self.kill( die, dump_state=False )

    def waiting_contact_task_ready( self, current_time ):
        result = False
        for itask in self.tasks:
            #print itask.id, current_time
            if itask.ready_to_run(current_time):
                result = True
                break
        return result

    def kill_cycle( self, ctime ):
        # kill all tasks currently at ctime
        task_ids = []
        for itask in self.tasks:
            if itask.c_time == ctime: # and itask.get_status() == 'waiting':
                task_ids.append( itask.id )

        self.kill( task_ids )

    def spawn_and_die_cycle( self, ctime ):
        # spawn and kill all tasks currently at ctime
        task_ids = {}
        for itask in self.tasks:
            if itask.c_time == ctime: # and itask.get_status() == 'waiting':
                task_ids[ itask.id ] = True

        self.spawn_and_die( task_ids )


    def spawn_and_die( self, task_ids, dump_state=True, reason='suicide by remote request' ):
        # spawn and kill all tasks in task_ids.keys()
        # works for dict or list input

        # TO DO: clean up use of spawn_and_die (the keyword args are clumsy)

        if dump_state:
            self.log.warning( 'pre-spawn-and-die state dump: ' + self.dump_state( new_file = True ))

        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.tasks:
                if t.id == id:
                    found = True
                    itask = t
                    break

            if not found:
                self.log.warning( "task to kill not found: " + id )
                return

            itask.log( 'DEBUG', reason )

            if not itask.state.has_spawned():
                # forcibly spawn the task and create its successor
                itask.state.set_spawned()
                itask.log( 'DEBUG', 'forced spawning' )

                new_task = itask.spawn( 'waiting' )
 
                if self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', 'STOPPING at configured stop time' )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.insert( new_task )
            else:
                # already spawned: the successor already exists
                pass

            # now kill the task
            self.trash( itask, reason )

    def kill( self, task_ids, dump_state=True ):
        # kill without spawning all tasks in task_ids
        if dump_state:
            self.log.warning( 'pre-kill state dump: ' + self.dump_state( new_file = True ))
        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.tasks:
                if t.id == id:
                    found = True
                    itask = t
                    break
            if not found:
                self.log.warning( "task to kill not found: " + id )
                return
            self.trash( itask, 'by request' )

    def trash( self, task, reason ):
        # remove a task from the pool
        count = 0
        alerted = False
        while count < 10:
            # retry loop for Pyro protocol error (see below)
            count += 1
            try:
                self.pyro.disconnect( task )
            except NamingError:
                # HANDLE ATTEMPTED INSERTION OF A TASK THAT ALREADY EXISTS.
                self.log.critical( task.id + ' CANNOT BE REMOVED (no such task)' )
                # do not retry
                break
            except ProtocolError, x:
                # HANDLE MYSTERIOUS PYRO NAMESERVER PROBLEM (NIWA 11-12 SEPT 2010):
                # registering and deregistering objects from pyro-ns (and even use of 
                # 'pyro-nsc ping'!) caused occasional 'incompatible protocol version'
                # errors. Fixed by restarting pyro-ns, but cause unknown thus far.
                self.log.critical( task.id + ' CANNOT BE REMOVED (Pyro protocol error) ' + str( count ) + '/10' )
                if not alerted:
                    alerted = True
                    print x
                    self.log.critical( ' ... (a) Check your pyro installations are version compatible' )
                    self.log.critical( ' ... (b) Restart the Pyro Nameserver' )
            else:
                task.log( 'NORMAL', "removing from suite (" + reason + ")" )
                task.prepare_for_death()
                self.tasks.remove( task )
                del task
                # do not retry
                break

    def insert( self, task ):
        # insert a task into the pool
        count = 0
        alerted = False
        while count < 10:
            # retry loop for Pyro protocol error (see below)
            count += 1
            try:
                self.pyro.connect( task, task.id )
            except NamingError:
                # HANDLE ATTEMPTED INSERTION OF A TASK THAT ALREADY EXISTS.
                self.log.critical( task.id + ' CANNOT BE INSERTED (already exists)' )
                # do not retry
                break
            except ProtocolError, x:
                # HANDLE MYSTERIOUS PYRO NAMESERVER PROBLEM (NIWA 11-12 SEPT 2010):
                # registering and deregistering objects from pyro-ns (and even use of 
                # 'pyro-nsc ping'!) caused occasional 'incompatible protocol version'
                # errors. Fixed by restarting pyro-ns, but cause unknown thus far.
                self.log.critical( task.id + ' CANNOT BE INSERTED (Pyro protocol error) ' + str( count ) + '/10' )
                if not alerted:
                    alerted = True
                    print x
                    self.log.critical( ' ... (a) Check your pyro installations are version compatible' )
                    self.log.critical( ' ... (b) Restart the Pyro Nameserver' )
            else:
                task.log('NORMAL', "task proxy inserted" )
                self.tasks.append( task )
                # do not retry
                break
