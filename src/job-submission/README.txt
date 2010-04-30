
Python temporary files:

# tempfile.NamedTemporaryFile( delete=False ) creates a file and opens
# it, but delete=False is post python 2.6 and we still currently run 2.4
# on some platforms!  (auto-delete on close() will remove file before
# the 'at' command runs it!)

# tempfile.mktemp() is deprecated in favour of mkstemp() but the latter
# was also introduced at python 2.6.

Sudo: run task as owner

# /etc/sudoers must be configured to allow the cylc operator to submit 
# jobs as the task owner, e.g. by allowing sudo access to 'at', qsub, or
# loadleveler. 

# Reason for use of temporary files as the job to submit

# in the temporary file we set the execution environment before calling
# the task script BECAUSE getting environment variables past 'sudo' and
# 'at' and loadleveler is otherwise problematic.


#    def execute_local_BROKEN( self, command_list ):
#
#        #for entry in command_list:
#        #    print '---' + entry + '---'
#
#        # command_list must be: [ command, arg1, arg2, ...]
#        try:
#            retcode = subprocess.call( command_list, shell=True )
#            if retcode != 0:
#                # the command returned non-zero exist status
#                print >> sys.stderr, ' '.join( command_list ) + ' failed: ', retcode
#                sys.exit(1)
#
#        except OSError:
#            # the command was not invoked
#            print >> sys.stderr, 'ERROR: unable to execute ' + command_list
#            print >> sys.stderr, ' * Is [cylc]/bin in your $PATH?'
#            print >> sys.stderr, " * Are all cylc scripts executable?"
#            print >> sys.stderr, " * Have you run 'cylc configure' yet?"
#
#            #raise Exception( 'job launch failed: ' + task_name + ' ' + c_time )
