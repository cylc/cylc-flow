# THIS SPEC FILE DEFINES ALL LEGAL ENTRIES IN CYLC SUITE.RC FILES.
# LaTeX documentation is maintained below each item, in comments that
# are ignored during suite.rc parsing, but is and extracted during
# document processing (which strips off the leading '#>' characters). 
# ITEM DOCUMENTATION SHOULD BE UPDATED WHENEVER AN ITEM IS CHANGED.

#>\subsection{Top Level (global settings)}

title = string( default="No suite title given" )
#>The suite title is displayed in the gcylc
#> suite database window, and can also be retrieved from a suite at run
#> time using the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} ``No suite title given''
#>\end{myitemize}

description = string( default="No suite description given" )
#>The suite description can be retrieved by 
#>gcylc right-click menu and the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} ``No suite description given''
#>\end{myitemize}

job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=background )
#>The default job submission method for the suite. This
#>determines how cylc job scripts are executed when a task is
#>ready to run. See Section~\ref{JobSubmissionMethods}.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em legal values:} 
#>   \begin{myitemize}
#>       \item \lstinline=background= - direct subshell execution in the background 
#>       \item \lstinline=at_now= - the rudimentary Unix `at' scheduler
#>       \item \lstinline=loadleveler= - loadleveler generic
#>       \item \lstinline=ll_ecox= - loadleveler, NIWA EcoConnect environment
#>       \item \lstinline=ll_raw= - loadleveler for prepared script
#>   \end{myitemize}
#>\item {\em default:} \lstinline=background=
#>\item {\em individual task override:} yes
#>\end{myitemize}

use lockserver = boolean( default=True )
#>Use of the cylc lockserver prevents
#> invocation of multiple instances of the same
#> suite at the same time, or invocation of a task (using
#> \lstinline=cylc submit=) if the same task is already running in its
#> suite. It will only allow multiple instances of a suite to run under
#> different registration GROUP:NAMEs if the suite declares itself
#> capable of that (see \lstinline=suite.rc= item
#> ``allow multiple simultaneous instances'').
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} True
#>\end{myitemize}

use secure passphrase = boolean( default=False )
#>If True, any intervention in a
#> running suite will require use of a secure passphrase. The way this is 
#> implemented has little impact on the user - a passphrase stored with
#> secure permissions under \lstinline=$HOME/.cylc/security/GROUP:NAME=
#> is automatically used if it exists. It must be present in
#> any user account that needs access to the suite (if tasks run on a 
#> remote host for instance). The passphrase itself is never transferred
#> across the network (a secure MD5 checksum is).  This guarantees
#> security so long as your user account isn't breached.
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} False
#>\end{myitemize}

tasks to exclude at startup = force_list( default=list())
#> If specified, {\em tasks in the list will be excluded at startup} (or
#> restart). If an {\em inclusion} list is also specified,
#> only included tasks that are not excluded will be used. Excluded
#> tasks can still be inserted at run time. Excluded tasks, if they have
#> not been removed from the dependency graph, can still be depended on
#> by other tasks, in which case some manual triggering may be required.
#>\begin{myitemize}
#>\item {\em type:} list of task names
#>\item {\em section:} (top level)
#>\item {\em default:} empty
#>\end{myitemize}

tasks to include at startup = force_list( default=list() )
#> If specified, {\em tasks NOT in the list will be excluded at startup} (or
#> restart). If an {\em exclusion} list is also specified,
#> only included tasks that are not excluded will be used. Excluded
#> tasks can still be inserted at run time. Excluded tasks, if they have
#> not been removed from the dependency graph, can still be depended on
#> by other tasks, in which case some manual triggering may be required.
#>\begin{myitemize}
#>\item {\em type:} list of task names
#>\item {\em section:} (top level)
#>\item {\em default:} empty
#>\end{myitemize}

maximum runahead hours = integer( min=0, default=24 )
#>This is the maximum difference in cycle time
#>that cylc allows between the fastest and slowest task in the suite.
#>Cycling tasks with no prerequisites (most suites will not have any 
#>of these) will rapidly spawn ahead to the runahead limit. 
#> Clock-triggered tasks with no other prerequisites (most suites will
#> have some of these) will do the same, but only in catchup operation.
#>\begin{myitemize}
#>\item {\em type:} integer, minimum 0
#>\item {\em section:} (top level)
#>\item {\em default:} 24
#>\end{myitemize}

top level logging directory = string( default = '$HOME/.cylc/logging' )
#>The top-level directory under which cylc 
#> stores suite-specific scheduler log files.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/.cylc/logging=.
#>\end{myitemize}

roll log at startup = boolean( default=True )
#>Roll (i.e. relabel ordered backups and start anew)
#>the cylc suite log file, every time the suite is started or restarted.
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} True
#>\end{myitemize}

top level state dump directory = string( default = '$HOME/.cylc/state' )
#>The top-level directory under which cylc
#> stores suite-specific state dump files (which can be used to restart
#> a suite from an earlier state).
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/.cylc/state=
#>\end{myitemize}

number of state dump backups = integer( min=1, default=10 )
#> Length, in  number of changes, of the automatic rolling
#> archive of state dump files that allows you to restart a suite from a
#> previous state. 
#> Every time a task changes state cylc updates the state dump and rolls
#> previous states back one on the archive. 
#> You'll probably only ever need the latest (most recent) state dump,
#> which is automatically used in a restart, but any previous state 
#> still in the archive can be used. Additionally, special labeled 
#> state dumps are written out prior to actioning any suite
#> intervention command.
#>\begin{myitemize}
#>\item {\em type:} integer, minimum 1
#>\item {\em section:} (top level)
#>\item {\em default:} 10
#>\end{myitemize}

job submission log directory = string( default='$HOME/CylcLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME' )
#>The directory in which to put the stdout and stderr
#> log files for the job scripts submitted by cylc when a task is ready to run.
#> For monolithic tasks (which don't resubmit sub-jobs themselves) these will
#> be the complete job logs for the task.  For owned tasks, the suite
#> owner's home directory will be replaced by the task owner's.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)  
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/CylcLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME=
#>\end{myitemize}

pre-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em before} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes before the 
#> ``task started'' message so an abort here will not register as a task
#> failure - it will appear that the task is stuck in the submitted state.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} empty
#>\item {\em individual task override:} yes
#>\end{myitemize}

post-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em after} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes after the 
#> ``task finished'' message so an abort here will not register as a task
#> failure - it will appear that the task finished successfully.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} empty
#>\item {\em individual task override:} yes
#>\end{myitemize}

task submitted hook = string( default=None )
#>Script to call whenever a task is submitted.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task started hook = string( default=None )
#> Script to call whenever a task reports that it has started running.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:}  (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task finished hook = string( default=None )
#>Script to call whenever a task reports that it has finished successfully.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task failed hook = string( default=None )
#>Script to call whenever a task reports that it has failed.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task warning hook = string( default=None )
#>script to call whenever a task reports a warning message.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task submission failed hook = string( default=None )
#>Script to call whenever job submission fails
#> for a task (in which case it will not start running).
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task timeout hook = string( default=None )
#>Script to call whenever a task times out (in job submission or execution).
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task submission timeout minutes = float( default=None )
#>If a task fails to report that it has started 
#> this long after it was submitted, call the task timeout hook script.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

task execution timeout minutes = float( default=None )
#> If a task fails to report that it has completed
#> (or failed) this long after it reported that it had started running,
#> call the task timeout hook script.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{myitemize}

pre-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em before} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes before the 
#> ``task started'' message so an abort here will not register as a task
#> failure - it will appear that the task is stuck in the submitted state.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} empty
#>\item {\em individual task override:} yes
#>\end{myitemize}

post-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em after} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes after the 
#> ``task finished'' message so an abort here will not register as a task
#> failure - it will appear that the task finished successfully.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em default:} empty
#>\item {\em individual task override:} yes
#>\end{myitemize}

use suite blocking = boolean( default=False )
#>A `blocked' suite will refuse to
#> comply with subsequent intervention commands until deliberately
#> `unblocked'. This is a crude security measure to guard against
#> accidental intervention in your own suites. It may be useful when
#> running multiple suites at once, or when running particularly
#> important suites, but is disabled by default because it is
#> fundamentally annoying. (Consider also that any intervention
#> results in a special state dump from which you can restart the suite 
#> if you decide the intervention was a mistake).
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level) 
#>\item {\em default:} False
#>\end{myitemize}

owned task execution method = option( sudo, ssh, default=sudo )
#>The means by which the chosen job submission method is invoked for
#> tasks owned by users other than the suite owner.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em legal values:}
#>   \begin{myitemize}
#>        \item sudo
#>        \item ssh
#>   \end{myitemize}
#>\item {\em default:} \lstinline=sudo=
#>\end{myitemize}

ignore task owners = boolean( default=False )
#>This turns off special treatment of owned tasks
#> (namely invocation of the job submission method via sudo or ssh as owner).
#> Can be useful when testing such a suite outside of its normal operational
#> environment.
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} False
#>\end{myitemize}

use quick task elimination = boolean( default=True )
#>When removing finished tasks from the suite as
#> early as possible, take account of tasks known to have no downstream
#> dependents in later (as opposed to its own) forecast cycles.
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} True
#>\end{myitemize}

dummy mode only = boolean( default=False )
#>If True, cylc will abort cleanly if you try to run
#>the suite in real mode. Can be used for demo suites, for example, that
#> can't run for real because they've been copied out of their operational
#> environment.
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} False
#>\end{myitemize}

allow multiple simultaneous instances = boolean( default=False )
#>Declares that all suite is I/O unique per
#> suite registration - i.e.\ all I/O paths include the suite registration 
#> group and name so
#> that multiple instances of the same suite can be run at once 
#> (under different registrations) without interference. If not, 
#> the lockserver will not allow a second instance of the suite to start.
#>\begin{myitemize}
#>\item {\em type:} boolean
#>\item {\em section:} (top level)
#>\item {\em default:} False
#>\end{myitemize}

job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
#>The shell used to interpret
#>job scripts (i.e.\ the scripts submitted by cylc when a task is ready 
#>to run).  This potentially affects the way that \lstinline=suite.rc= 
#> environment sections are converted to scripting (currently hardwired
#> in cylc - would need to change this to use csh for example), and how
#> the user writes \lstinline=suite.rc= {\em scripting} sections.
#>\begin{myitemize}
#>\item {\em type:} string
#>\item {\em section:} (top level)
#>\item {\em legal values:}
#>   \begin{myitemize}
#>        \item \lstinline=/bin/bash=
#>        \item \lstinline=/bin/ksh=
#>        \item \lstinline=/usr/bin/bash=
#>        \item \lstinline=/usr/bin/ksh=
#>   \end{myitemize}
#>\item {\em default:} \lstinline=/bin/bash= 
#>\end{myitemize}

[dummy mode]
# dummy mode was most useful prior to cylc-3: it allowed us to get the
# scheduling right without running real tasks when a suite was defined
# entirely by a collection of distinct "task definition files" whose
# prerequisites and outputs had to be consistent across the suite.
# Now (post cylc-3) it is primarily useful for cylc development, and
# for generating run-time dependency graphs very quickly.
clock offset from initial cycle time in hours = integer( default=24 )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [dummy mode]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

clock rate in seconds per dummy hour = integer( default=10 )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [dummy mode]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [dummy mode]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [dummy mode]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[special tasks]
    startup = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [special tasks]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    coldstart = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    oneoff = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    sequential = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    # outputs MUST contain the word 'restart':
    models with explicit restart outputs = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    # offset can be a float:
    clock-triggered = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[task families]
    __many__ = force_list( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [task families]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[dependencies]
    # dependency graphs under cycle time lists:
    [[__many__]]
    graph = string
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [dependencies][[(hours)]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[experimental]
# generate a distinct graph for each timestep
live graph movie = boolean( default=False )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [experimental]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[visualization]
# hours after which to stop plotting the run time graph
when to stop updating = integer( default=24 )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

# absolute, or relative to $CYLC_SUITE_DIR for portability
run time graph directory = string( default='$CYLC_SUITE_DIR/graphing')
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

run time graph filename  = string( default='runtime.dot')
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

# TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS
show family members = boolean( default=False )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

use node color for edges = boolean( default=True )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=ellipse'))
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

default edge attributes = force_list( default=list('color=black'))
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[[node groups]]
    __many__ = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization][[node groups]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

[[node attributes]]
    # item is task name or task group name
    __many__ = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [visualization][[node attributes]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[task insertion groups]
 __many__ = force_list()
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [task insertion groups]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[environment]
__many__ = string
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [environment]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


# Global directives.
# Prefix ('# @') and final directive ('# @ queue') supplied by job submission method.
[directives]
__many__ = string
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [directives]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


# CONFIGOBJ or VALIDATE BUG? LIST CONSTRUCTOR FAILS IF LAST LIST ELEMENT
# IS FOLLOWED BY A SPACE (OR DOES IT JUST NEED A TRAILING COMMA?):
#   GOOD:
# foo = string_list( default=list('foo','bar'))
#   BAD:
# bar = string_list( default=list('foo','bar' ))

[tasks]
    # new style suite definition: dependency graph plus minimal task info
    [[__many__]]
    description = string( default="No task description supplied" )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    job submission log directory = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    pre-command scripting = string( default='' )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em default:} empty
#>\end{myitemize}

    post-command scripting = string( default='' )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em default:} empty
#>\end{myitemize}


    task submitted hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task started hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task finished hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task failed hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task warning hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task submission failed hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task timeout hook = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    task submission timeout minutes = float( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    execution timeout minutes = float( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    reset execution timeout on incoming messages = boolean( default=True )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    # default to dummy task:
    command = force_list( default=list( cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    owner = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    host = string( default=None )
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    # hours required to use ('submit' or 'insert') tasks not in the
    # graph; if present graphed hours must not conflict with this.
    hours = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

    extra log files = force_list( default=list())
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

        [[[environment]]]
        __many__ = string
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]][[[environment]]]
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

        [[[directives]]]
        # Prefix ('# @') and final directive ('# @ queue') supplied 
        # by job submission method.
        __many__ = string
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} 
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

          [[[outputs]]]
        __many__ = string
#>\begin{myitemize}
#>\item {\em type:}
#>\item {\em section:} 
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


