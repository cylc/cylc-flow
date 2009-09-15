#!/usr/bin/python

import reference_time
import pimp_my_logger
import logging
#import pdb
import os
import re
from broker import broker

class manager:
    def __init__( self, config, dummy_mode, pyro, clock, restart, restart_statedump = None ):
        
        self.dummy_mode = dummy_mode
        self.pyro = pyro  # pyrex (cyclon Pyro helper) object
        self.log = logging.getLogger( "main" )

        self.clock = clock

        self.stop_time = config.get('stop_time')
 
        self.config = config

        self.system_hold_now = False
        self.system_hold_reftime = None

        # initialise the dependency broker
        self.broker = broker()
        
        # instantiate the initial task list and create task logs 
        self.tasks = []
        if restart:
            self.load_from_state_dump( restart_statedump )
        else:
            self.load_from_config()

    def set_stop_time( self, stop_time ):
        self.log.debug( "Setting new stop time: " + stop_time )
        self.stop_time = stop_time

    def set_system_hold( self, reftime = None ):
        if reftime:
            self.system_hold_reftime = reftime
            self.log.critical( "SETTING SYSTEM HOLD: no new tasks will run from " + reftime )
        else:
            self.system_hold_now = True
            self.log.critical( "SETTING SYSTEM HOLD: won't run any more tasks")

    def unset_system_hold( self ):
        self.log.critical( "UNSETTING SYSTEM HOLD: new tasks will run when ready")
        self.system_hold_now = False
        self.system_hold_reftime = None

    def get_task_instance( self, module, class_name ):
        # task object instantiation by module and class name
	    mod = __import__( module )
	    return getattr( mod, class_name)

    def get_oldest_ref_time( self ):
        oldest = 9999887766
        for itask in self.tasks:
            if int( itask.ref_time ) < int( oldest ):
                oldest = itask.ref_time
        return oldest

    def load_from_config ( self ):
        # load initial system state from configured tasks and start time
        #--
        print '\nCLEAN START: INITIAL STATE FROM CONFIGURED TASK LIST\n'
        self.log.info( 'Loading state from configured task list' )
        # config.task_list = [ taskname1, taskname2, ...]

        start_time = self.config.get('start_time')

        for name in self.config.get('task_list'):

            # instantiate the task
            itask = self.get_task_instance( 'task_classes', name )( start_time )

            # create the task log
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, self.config, self.dummy_mode, self.clock )

            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.stop_time:
                if int( itask.ref_time ) > int( self.stop_time ):
                    itask.log( 'WARNING', "STOPPING at " + self.stop_time )
                    itask.prepare_for_death()
                    del itask
                    skip = True

            if not skip:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.get_identity() )
                self.tasks.append( itask )


    def load_from_state_dump( self, filename = None ):
        # load initial system state from the configured state dump file
        #--
        configured_file = self.config.get('state_dump_file')
        if filename:
            if filename == os.path.basename( filename ):
                # is a plain filename; append to configured path
                dirname = os.path.dirname( configured_file )
                filename = dirname + '/' + filename
            elif re.match( '^/' ):
                # is an absolute path
                pass
            else:
                # relative path; append to cwd
                filename = os.getcwd() + '/' + filename

        else:
            filename = configured_file

        # The state dump file format is:
        # system time <time>
        # class <classname>: item1=value1, item2=value2, ... 
        # <ref_time> : <taskname> : <state>
        # <ref_time> : <taskname> : <state>
        #    (and so on)
        # The time format is defined by the clock.reset()
        # task <state> format is defined by task_state.dump()

        self.log.info( 'Loading previous state from ' + filename )

        FILE = open( filename, 'r' )
        lines = FILE.readlines()
        FILE.close()

        # reset time first (only has an effect in dummy mode)
        [ junk, time ] = lines[0].split( ' : ' )
        self.clock.reset( time )

        log_created = {}

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
            [ ref_time, name, state ] = line.split(' : ')

            # instantiate the task object
            itask = self.get_task_instance( 'task_classes', name )( ref_time, state )

            # create the task log
            if name not in log_created.keys():
                log = logging.getLogger( 'main.' + name )
                pimp_my_logger.pimp_it( log, name, self.config, self.dummy_mode, self.clock )
                log_created[ name ] = True
 
            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.stop_time:
                if int( itask.ref_time ) > int( self.stop_time ):
                    itask.log( 'WARNING', " STOPPING at " + self.stop_time )
                    itask.prepare_for_death()
                    del itask
                    skip = True

            if not skip:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.get_identity() )
                self.tasks.append( itask )

    def no_tasks_running( self ):
        # return True if no tasks are running
        #--
        for itask in self.tasks:
            if itask.state.is_running():
                return False
        return True

    def all_tasks_finished( self ):
        # return True if all tasks have finished AND abdicated
        #--
        for itask in self.tasks:
            if not itask.state.is_finished() or not itask.state.has_abdicated():
                return False
        return True


    def negotiate_dependencies( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        #--
    
        # Instead: O(n) BROKERED NEGOTIATION

        self.broker.reset()

        for itask in self.tasks:
            # register task outputs
            self.broker.register( itask.get_identity(), itask.outputs )

        # for debugging;            
        # self.broker.dump()

        for itask in self.tasks:
            # get the broker to satisfy tasks prerequisites
            self.broker.negotiate( itask.prerequisites )

    def run_tasks( self, launcher ):
        # tell each task to run if it is ready
        # unless the system is on hold
        #--
        if self.system_hold_now:
            # general system hold
            self.log.debug( 'not asking any tasks to run (general system hold in place)' )
            return

        for itask in self.tasks:
                if self.system_hold_reftime:
                    if int( itask.ref_time ) >= int( self.system_hold_reftime ):
                        self.system_hold_now = True
                        self.log.debug( 'not asking ' + itask.get_identity() + ' to run (' + self.system_hold_reftime + ' hold in place)' )
                        continue

                itask.run_if_ready( launcher, self.clock )

    def regenerate_tasks( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) abdicates
        #--

        # update oldest system reference time
        oldest_ref_time = self.get_oldest_ref_time()

        for itask in self.tasks:

            tdiff = reference_time.decrement( itask.ref_time, self.config.get('max_runahead_hours') )
            if int( tdiff ) > int( oldest_ref_time ):
                # too far ahead: don't abdicate this task.
                itask.log( 'DEBUG', "delaying abdication (too far ahead)" )
                continue

            if itask.abdicate():
                itask.log( 'DEBUG', 'abdicating')

                # dynamic task object creation by task and module name
                new_task = self.get_task_instance( 'task_classes', itask.name )( itask.next_ref_time() )
                if self.stop_time and int( new_task.ref_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.pyro.connect( new_task, new_task.get_identity() )
                    new_task.log('DEBUG', "connected" )
                    self.tasks.append( new_task )


    def dump_state( self, new_file = False ):
        filename = self.config.get('state_dump_file')
        if new_file:
            filename += '.' + self.clock.dump_to_str()

        # system time
        FILE = open( filename, 'w' )
        FILE.write( 'system time : ' + self.clock.dump_to_str() + '\n' )

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

    def earliest_unabdicated( self ):
        all_abdicated = True
        earliest_unabdicated = None
        for itask in self.tasks:
            if not itask.state.has_abdicated():
                all_abdicated = False
                if not earliest_unabdicated:
                    earliest_unabdicated = itask.ref_time
                elif int( itask.ref_time ) < int( earliest_unabdicated ):
                    earliest_unabdicated = itask.ref_time

        return [ all_abdicated, earliest_unabdicated ]

    def earliest_unsatisfied( self ):
        # find the earliest unsatisfied task
        all_satisfied = True
        earliest_unsatisfied = None
        for itask in self.tasks:
            if not itask.prerequisites.all_satisfied():
                all_satisfied = False
                if not earliest_unsatisfied:
                    earliest_unsatisfied = itask.ref_time
                elif int( itask.ref_time ) < int( earliest_unsatisfied ):
                    earliest_unsatisfied = itask.ref_time

        return [ all_satisfied, earliest_unsatisfied ]

    def earliest_unfinished( self ):
        # find the earliest unfinished task
        all_finished = True
        earliest_unfinished = None
        for itask in self.tasks:
            if not itask.state.is_finished():
                all_finished = False
                if not earliest_unfinished:
                    earliest_unfinished = itask.ref_time
                elif int( itask.ref_time ) < int( earliest_unfinished ):
                    earliest_unfinished = itask.ref_time

        return [ all_finished, earliest_unfinished ]

    def kill_spent_tasks( self ):
        # Delete tasks that are no longer needed, i.e. those that:
        #   (1) have finished and abdicated, 
        #       AND
        #   (2) are no longer needed to satisfy prerequisites.

        # Also, do not delete any task with the same reference time 
        # as a failed task, because these could be needed to satisfy the
        # failed task when it gets re-run after the problem is fixed.
        #--

        # A/ QUICK DEATH TASKS
        # Tasks with 'quick_death = True', by definition they have only
        # cotemporal downstream dependents, so they are no longer needed
        # to satisfy prerequisites once all their cotemporal peers have
        # finished. The only complication is that new cotemporal peers
        # can appear, in principle, so long as there are unabdicated
        # tasks with earlier reference times. Therefore they are spent 
        # IF finished-and-abdicated AND there are no unabdicated tasks
        # at the same reference time or earlier.
        #--

        # find the earliest unabdicated task, 
        # and ref times of any failed tasks. 
        failed_rt = {}
        for itask in self.tasks:
            if itask.state.is_failed():
                failed_rt[ itask.ref_time ] = True

        [all_abdicated, earliest_unabdicated] = self.earliest_unabdicated()
        if all_abdicated:
            self.log.debug( "all tasks abdicated")
        else:
            self.log.debug( "earliest unabdicated task at: " + earliest_unabdicated )

        # find the spent quick death tasks
        spent = []
        for itask in self.tasks:
            if not itask.done():
                continue
            if itask.ref_time in failed_rt.keys():
                continue

            if itask.quick_death and not all_abdicated: 
                if all_abdicated or int( itask.ref_time ) < int( earliest_unabdicated ):
                    spent.append( itask )
 
        # delete the spent quick death tasks
        for itask in spent:
            self.tasks.remove( itask )
            self.pyro.disconnect( itask )
            itask.log( 'NORMAL', "disconnected (spent; quickdeath)" )
            itask.prepare_for_death()

        del spent

        # B/ THE GENERAL CASE
        # No finished-and-abdicated task that is later than the earliest
        # unsatisfied task can be deleted yet because it may still be
        # needed to satisfy new tasks that may appear when earlier (but
        # currently unsatisfied) tasks abdicate. Therefore only
        # finished-and-abdicated tasks that are earlier than the
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

        # THEREFORE the correct deletion cutoff is 'earliest unfinished'
        # (members of which will remain in, or be reset to, the waiting
        # state on a restart. The only way to use 'earliest unsatisfied'
        # over a restart would be to record the state of all
        # prerequisites for each task in the state dump - THIS MAY BE A
        # GOOD THING TO DO, HOWEVER!

        #[ all_satisfied, earliest_unsatisfied ] = self.earliest_unsatisfied()
        #if all_satisfied:
        #    self.log.debug( "all tasks satisfied" )
        #else:
        #    self.log.debug( "earliest unsatisfied: " + earliest_unsatisfied )

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

            if itask.ref_time in failed_rt.keys():
                continue

            #if not all_satisfied:
            #    if int( itask.ref_time ) >= int( earliest_unsatisfied ):
            #        continue
            if not all_finished:
                if int( itask.ref_time ) >= int( earliest_unfinished ):
                    continue
            
            if itask.ref_time in candidates.keys():
                candidates[ itask.ref_time ].append( itask )
            else:
                candidates[ itask.ref_time ] = [ itask ]

        # searching from newest tasks to oldest, after the earliest
        # unsatisfied task, find any done task types that appear more
        # than once - the second or later occurrences can be deleted.
        reftimes = candidates.keys()
        reftimes.sort( key = int, reverse = True )
        seen = {}
        spent = []
        for rt in reftimes:
            #if not all_satisfied:
            #    if int( rt ) >= int( earliest_unsatisfied ):
            #        continue
            if not all_finished:
                if int( rt ) >= int( earliest_unfinished ):
                    continue
            
            for itask in candidates[ rt ]:
                try:
                    # oneoff non quick death tasks need to nominate 
                    # the task type that will take over from them.
                    # (otherwise they will never be deleted).
                    name = itask.oneoff_follow_on
                except AttributeError:
                    name = itask.name

                if name in seen.keys():
                    # already seen this guy, so he's spent
                    spent.append( itask )
                else:
                    # first occurence
                    seen[ name ] = True
            
        # now delete the spent tasks
        for itask in spent:
            self.tasks.remove( itask )
            self.pyro.disconnect( itask )
            itask.log( 'NORMAL', "disconnected (spent; general)" )
            itask.prepare_for_death()

        del spent


    def reset_task( self, task_id ):
        found = False
        for itask in self.tasks:
            if itask.get_identity() == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to waiting state" )
            itask.state = 'waiting'
            itask.prerequisites.set_all_unsatisfied()
            itask.outputs.set_all_incomplete()
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def insertion( self, ins ):
        # insert a new task or task group in a waiting state

        if re.match( '^GROUP:', ins ):
            # task group
            [ junk, group ] = ins.split(':')
            [ groupname, ref_time ] = group.split( '%' )

            try:
                tasknames = self.config.get( 'task_groups')[groupname]
            except KeyError:
                self.log.warning( 'insertion group ' + groupname + ' not defined' )
                return

            ids = []
            for name in tasknames:
                ids.append( name + '%' + ref_time )

        else:
            # single task id
            ids = [ ins ]


        for task_id in ids:
            [ name, ref_time ] = task_id.split( '%' )

            # instantiate the task object
            itask = self.get_task_instance( 'task_classes', name )( ref_time )

            if itask.instance_count == 1:
                # first task of its type, so create the log
                log = logging.getLogger( 'main.' + name )
                pimp_my_logger.pimp_it( log, name, self.config, self.dummy_mode, self.clock )
 
            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.stop_time:
                if int( itask.ref_time ) > int( self.stop_time ):
                    itask.log( 'WARNING', " STOPPING at " + self.stop_time )
                    itask.prepare_for_death()
                    del itask
                    skip = True

            if not skip:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.get_identity() )
                self.tasks.append( itask )


    def dump_task_requisites( self, task_ids ):
        for id in task_ids.keys():
            # find the task
            found = False
            itask = None
            for t in self.tasks:
                if t.get_identity() == id:
                    found = True
                    itask = t
                    break

            if not found:
                self.log.warning( 'task not found for remote requisite dump request: ' + id )
                return

            itask.log( 'DEBUG', 'dumping requisites to stdout, by remote request' )

            print
            print 'PREREQUISITE DUMP', itask.get_identity() 
            itask.prerequisites.dump()
            print
            print 'OUTPUT DUMP', itask.get_identity() 
            itask.outputs.dump()
            print

    def find_cotemporal_dependees( self, parent ):
        # recursively find the group of all cotemporal tasks that depend
        # directly or indirectly on parent

        deps = {}
        for itask in self.tasks:
            if itask.ref_time != parent.ref_time:
                # not cotemporal
                continue

            if itask.prerequisites.will_satisfy_me( parent.outputs, parent.get_identity() ):
                #print 'dependee: ' + itask.get_identity()
                deps[ itask ] = True

        for itask in deps:
            res = self.find_cotemporal_dependees( itask )
            deps = self.addDicts( res, deps ) 

        deps[ parent ] = True

        return deps


    def addDicts(self, a, b):
        c = {}
        for item in a:
            c[item] = a[item]
            for item in b:
                c[item] = b[item]
        return c


    def purge( self, id, stop ):
        # recursively abdicate and kill a task and its dependees, down
        # to the given stop time

        # find the task
        found = False
        for itask in self.tasks:
            if itask.get_identity() == id:
                found = True
                next = itask.next_ref_time()
                name = itask.name
                break

        if not found:
            self.log.warning( 'task to purge not found: ' + id )
            return

        # find then abdicate and kill all cotemporal dependees
        condemned = self.find_cotemporal_dependees( itask )
        cond = {}
        for itask in condemned:
            cond[ itask.get_identity() ] = True
        
        self.abdicate_and_kill( cond )

        # now do the same for the next instance of the task
        if int( next ) <= int( stop ):
            self.purge( name + '%' + next, stop )


    def abdicate_and_kill_rt( self, reftime ):
        # abdicate and kill all WAITING tasks currently at reftime
        # (use to kill lame tasks that will never run because some
        # upstream dependency has failed).
        task_ids = {}
        for itask in self.tasks:
            if itask.ref_time == reftime and itask.state == 'waiting':
                task_ids[ itask.get_identity() ] = True

        self.abdicate_and_kill( task_ids )

 
    def abdicate_and_kill( self, task_ids ):
        # abdicate and kill all tasks in task_ids.keys()
        for id in task_ids.keys():
            # find the task
            found = False
            itask = None
            for t in self.tasks:
                if t.get_identity() == id:
                    found = True
                    itask = t
                    break

            if not found:
                self.log.warning( "task to kill not found: " + id )
                return

            itask.log( 'DEBUG', "killing myself by remote request" )

            if not itask.state.has_abdicated():
                # forcibly abdicate the task and create its successor
                itask.set_abdicated()
                itask.log( 'DEBUG', 'forced abdication' )
                # TO DO: the following should reuse code in regenerate_tasks()?
                # dynamic task object creation by task and module name
                new_task = self.get_task_instance( 'task_classes', itask.name )( itask.next_ref_time() )
                if self.stop_time and int( new_task.ref_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', 'STOPPING at configured stop time' )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.pyro.connect( new_task, new_task.get_identity() )
                    new_task.log( 'DEBUG', 'connected' )
                    self.tasks.append( new_task )

            else:
                # already abdicated: the successor already exists
                pass

            # now kill the task
            self.tasks.remove( itask )
            self.pyro.disconnect( itask )
            itask.log( 'WARNING', "disconnected (remote request)" )
            itask.prepare_for_death()
            del itask
