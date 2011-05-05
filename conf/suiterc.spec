# THIS SPEC FILE DEFINES ALL LEGAL ENTRIES IN CYLC SUITE.RC FILES.
# LaTeX documentation is maintained below each item, in comments that
# are ignored during suite.rc parsing, but is and extracted during
# document processing (which strips off the leading '#>' characters). 
# ITEM DOCUMENTATION SHOULD BE UPDATED WHENEVER AN ITEM IS CHANGED.


# NOTE: A CONFIGOBJ or VALIDATE BUG? LIST CONSTRUCTOR FAILS IF LAST LIST
# ELEMENT IS FOLLOWED BY A SPACE (OR DOES IT JUST NEED A TRAILING COMMA?):
#   GOOD:
# foo = string_list( default=list('foo','bar'))
#   BAD:
# bar = string_list( default=list('foo','bar' ))


#>\subsection{Top Level (global settings)}

title = string( default="No title supplied" )
#>The suite title is displayed in the gcylc
#> suite database window, and can also be retrieved from a suite at run
#> time using the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} ``No title supplied''
#>\end{myitemize}

description = string( default="No description supplied" )
#>The suite description can be retrieved by 
#>gcylc right-click menu and the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} ``No description supplied''
#>\end{myitemize}

job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=background )
#>The default job submission method for the suite. This
#>determines how cylc job scripts are executed when a task is
#>ready to run. See Section~\ref{JobSubmissionMethods}.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:} 
#>   \begin{myitemize}
#>       \item \lstinline=background= - direct subshell execution in the background 
#>       \item \lstinline=at_now= - the rudimentary Unix `at' scheduler
#>       \item \lstinline=loadleveler= - loadleveler generic
#>       \item \lstinline=ll_ecox= - loadleveler, NIWA EcoConnect environment
#>       \item \lstinline=ll_raw= - loadleveler for prepared script
#>   \end{myitemize}
#>\item {\em default:} \lstinline=background=
#>\item {\em specific task override:} yes
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
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
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
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
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
#>\item {\em section:} (top level)
#>\item {\em type:} list of task names
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
#>\item {\em section:} (top level)
#>\item {\em type:} list of task names
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
#>\item {\em section:} (top level)
#>\item {\em type:} integer
#>\item {\em legal values:} $>= 0$
#>\item {\em default:} 24
#>\end{myitemize}

top level logging directory = string( default = '$HOME/.cylc/logging' )
#>The top-level directory under which cylc 
#> stores suite-specific scheduler log files.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/.cylc/logging=.
#>\end{myitemize}

roll log at startup = boolean( default=True )
#>Roll (i.e. relabel ordered backups and start anew)
#>the cylc suite log file, every time the suite is started or restarted.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\end{myitemize}

top level state dump directory = string( default = '$HOME/.cylc/state' )
#>The top-level directory under which cylc
#> stores suite-specific state dump files (which can be used to restart
#> a suite from an earlier state).
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
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
#>\item {\em section:} (top level)
#>\item {\em type:} integer
#>\item {\em legal values:} $>= 1$
#>\item {\em default:} 10
#>\end{myitemize}

job submission log directory = string( default='$HOME/CylcLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME' )
#>The directory in which to put the stdout and stderr
#> log files for the job scripts submitted by cylc when tasks are ready to run.
#> For monolithic tasks (which don't resubmit sub-jobs themselves) these will
#> be the complete job logs for the task.  For owned tasks, the suite
#> owner's home directory will be replaced by the task owner's.
#>\begin{myitemize}
#>\item {\em section:} (top level)  
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/CylcLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME=
#>\end{myitemize}

#>IGNORE
task submitted hook = string( default=None )
task submission failed hook = string( default=None )
task started hook = string( default=None )
task finished hook = string( default=None )
task failed hook = string( default=None )
task warning hook = string( default=None )
task timeout hook = string( default=None )
#>RESUME

#> \subsubsection{task EVENT hooks}
#> Task event hooks facilitate centralized alerting for critical events
#> in operational suites. You can name script(s) to attach to various 
#> events using one or more of the following items:
#>\begin{myitemize}
#>\item {\bf task submitted hook}
#>\item {\bf task submission failed hook}
#>\item {\bf task started hook}
#>\item {\bf task finished hook}
#>\item {\bf task failed hook}
#>\item {\bf task timeout hook}
#>\end{myitemize}
#> These set global defaults that can be overridden by specific tasks.
#> Hook scripts are called with the following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [EVENT] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where MESSAGE will describe what has happened.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} None
#>\item {\em specific task override:} yes
#>\end{myitemize}

#>IGNORE
task submission timeout minutes = float( default=None )
task execution timeout minutes = float( default=None )
#>RESUME

#> \subsubsection{task ACTION timeout minutes}
#>You can set timeout intervals for submission or execution with
#>the following items:
#>\begin{myitemize}
#>\item {\bf task submission timeout minutes}
#>\item {\bf task execution timeout minutes}
#>\end{myitemize}
#> If a task has not started (or finished) N minutes after it was submitted 
#> (or started), the task timeout hook script will be called with the
#> following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [ACTION] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where ACTION is `submission' or `execution'.
#> As for the hook scripts themselves, these global settings
#> can be overridden by specific tasks.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} float (minutes)
#>\item {\em default:} None
#>\item {\em specific task override:} yes
#>\end{myitemize}

reset execution timeout on incoming messages = boolean( default=True )
#> If True, and you have set an execution timeout, the timer will 
#> reset to zero every time a message is received from a running task.
#> Otherwise, the task will timeout if it does not finish in time,
#> even if it last sent a message (and was therefore still alive) 
#> within the initial timeout interval.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em specific task override:} yes
#>\end{myitemize}

pre-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em before} the task command, for every task. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes before the 
#> ``task started'' message so an abort here will not register as a task
#> failure - it will appear that the task is stuck in the submitted state.
#> If task-specific pre-command scripting is also defined for particular
#> tasks, the global scripting will be executed first.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} empty
#>\end{myitemize}

post-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em after} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes after the 
#> ``task finished'' message so an abort here will not register as a task
#> failure - it will appear that the task finished successfully.
#> If task-specific post-command scripting is also defined for particular
#> tasks, the global scripting will be executed first.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} empty
#>\item {\em specific task override:} yes
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
#>\item {\em section:} (top level) 
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

owned task execution method = option( sudo, ssh, default=sudo )
#>The means by which the chosen job submission method is invoked for
#> tasks owned by users other than the suite owner.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
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
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

use quick task elimination = boolean( default=True )
#>When removing finished tasks from the suite as
#> early as possible, take account of tasks known to have no downstream
#> dependents in later (as opposed to its own) forecast cycles.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\end{myitemize}

dummy mode only = boolean( default=False )
#>If True, cylc will abort cleanly if you try to run
#>the suite in real mode. Can be used for demo suites, for example, that
#> can't run for real because they've been copied out of their operational
#> environment.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
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
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
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
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:}
#>   \begin{myitemize}
#>        \item \lstinline=/bin/bash=
#>        \item \lstinline=/bin/ksh=
#>        \item \lstinline=/usr/bin/bash=
#>        \item \lstinline=/usr/bin/ksh=
#>   \end{myitemize}
#>\item {\em default:} \lstinline=/bin/bash= 
#>\end{myitemize}

[special tasks]
#> The default cylc task starts running as soon as its prerequisites are
#> satisfied, and automatically spawns a successor as soon as
#> it starts running - so that successive instances can run in
#> parallel if the opportunity arises. This section lists any tasks
#> whose behaviour should differ from this.

    clock-triggered = force_list( default=list())
#> A list of {\em clock-triggered tasks} in the suite. These are 
#> tasks that must wait on a wall clock time, specified
#> as an offset from their own cycle times, in addition to its dependence on
#> other tasks (if any), before they can run. This should be used
#> for tasks that detect the arrival or availability of external real
#> time data required by other tasks in the suite. If the trigger time has
#> already passed, when catching up after a delay in operations for example,
#> the task can run as soon as they appear in the suite.
#>\begin{myitemize}
#>\item {\em section:}  [special tasks]
#>\item {\em type:} list of `taskname(offset)'
#>\item {\em legal values:} offset in hours (float - decimal fractions - OK)
#>\item {\em default:} None
#>\end{myitemize}

    startup = force_list( default=list())
#> A list of all {\em startup tasks} in the suite. These are tasks that
#> are only used in a suite cold start
#> (i.e.\ starting `from scratch'). This can be used to create a 
#> task that cleans out or prepares a suite workspace at the
#> beginning of a run, for instance. {\em Note that this is different
#> from a ``coldstart task''} (next item).
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

    coldstart = force_list( default=list())
#> A list of all {\em coldstart tasks} in the suite. a A coldstart task
#> is a oneoff task used to satisfy some task's dependence on
#> another task from a previous cycle. The main
#> use of coldstart tasks is to satisfy the initial restart dependencies
#> of warm cycled forecast models, wherein the coldstart task may run an
#> actual cold start forecast; but the same principle applies for any
#> task that depends on a previous cycle (because in a suite suite coldstart
#> there obviously is no previous cycle). Coldstart tasks can also be
#> inserted into a suite at run time in order to "re-coldstart" some
#> part of the suite that had to skip a few cycles due to problems of
#> some kind.
# TO DO: EXPLAIN MULTI-TASK COLD START PROCESSES?
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

    oneoff = force_list( default=list())
#> A list of all {\em oneoff tasks} in the suite. These tasks do not
#> spawn a successor - they run once and are then
#> eliminated from the suite. {\em Startup} and {\em
#> coldstart} tasks are automatically oneoff tasks.
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

    sequential = force_list( default=list())
#> A list of all {\em sequential tasks} in the suite.  These tasks do
#> not spawn a successor until they have finished running.
#>\begin{myitemize}
#>\item {\em section:}  [special tasks]
#>\item {\em type:} list of task names
#>\item {\em legal values:}
#>\item {\em default:} empty list
#>\end{myitemize}
#>  This should be used for:
#>\begin{myitemize}
#>    \item {\em tasks that cannot run in parallel with their own previous
#> instances} because they would somehow interfere with each other 
#> (use cycle time in all I/O paths to avoid this). 
#>    \item {\em Warm cycled models that write out restart files for multiple
#>      cycles ahead} (except: see ``models with explicit restart outputs'' below).
#>     Why? Because you don't want Model(T) waiting around
#>     to trigger off Model(T-12), if other prerequisites are satisfied,
#> when Model(T-6) has not finished yet. If Model is 
#>     forced to be sequential, this can't happen because Model(T) won't exist 
#>     in the suite until Model(T-6) has finished. But if Model(T-6) fails, it
#>     can be spawned-and-removed from the suite so that Model(T) can then
#>     trigger off Model(T-12) (if it's restart prerequisites allow that). 
#>\end{myitemize}

    models with explicit restart outputs = force_list( default=list())
#> {\em This is only required in the unlikely event that you want a warm
#> cycled forecast model to be able to start at the instant its restart
#> files are ready (if other prerequisites are satisfied) BEFORE
#> its previous instance has finished.}  If so, the task has to depend
#> on a special output message emitted by the previous instance as soon as
#> its restart files are ready, instead of just on the previous instance
#> finishing. Tasks so identified here must define the output messages
#> in the task outputs section - see Section~\ref{ExplicitOutputs}.
# TO DO: THESE TASKS COULD BE IDENTIFIED FROM THE GRAPH?
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

[task families]
    __many__ = force_list( default=None )
#>\begin{myitemize}
#>\item {\em section:} [task families]
#>\item {\em type:}
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
#>\item {\em section:} [dependencies][[(hours)]]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[environment]
#> Use this section to define the global task execution environment, i.e.\
#> environment variables made available to all tasks. Order of definition 
#> is preserved. See ``Task Execution Environment'', 
#> Section~\ref{TaskExecutionEnvironment} for more information.
__many__ = string
#> Repeat for as many variables as you need.
#>\begin{myitemize}
#>\item {\em section:} [environment]
#>\item {\em type:} string
#>\item {\em legal values:} any valid environment variable assignment
#> expression. Whitespace around the `$=$' is fine (the
#> \lstinline=suite.rc= file is not a shell script). 
#> E.g. for the bash shell: 
#>   \begin{myitemize}
#>       \item \lstinline@FOO = $HOME/bar/baz@
#>       \item \lstinline@BAR = ${FOO}$GLOBALVAR@
#>       \item \lstinline@BAZ = $(echo "hello world")@
#>       \item \lstinline@WAZ = ${FOO%.jpg}.png@
#>   \end{myitemize}
#>\item {\em default:} None
#>\end{myitemize}

[directives]
#> Use this section to define batch queue scheduler `directives' 
#> for all tasks in the suite (for {\em loadleveler} or {\em torque}, etc.).
#> These end up near the top of the job script cylc submits when a
#> task is ready to run. Whether or not items defined here are used
#> depends on the task's job submission method. The job
#> submission method should also define the directive comment prefix
#> (`\lstinline=# @=' for loadleveler) and final directive ('\lstinline=# @ queue=').
__many__ = string
#> Repeat for as many directives as you need.
#>\begin{myitemize}
#>\item {\em section:} [directives]
#>\item {\em type:} string
#>\item {\em legal values:} any legal directive for your batch scheduler
#>\item {\em default:} None
#>\end{myitemize}

[tasks]
    [[__many__]]
#> Repeat this section for every task in the suite.

    description = string( default="No description supplied" )
#> A description of what this task does; it can be retrieved at run time
#> by the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} No description supplied
#>\end{myitemize}

    command = force_list( default=list( cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
#> The commandline to execute when this task is ready to run. It may refer to variables in the
#> task execution environment (cylc-supplied, or user-defined global and task-specific). If 
#> the command is omitted or commented out the task will run as a dummy task.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} \lstinline=cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP= (dummy task)
#>\end{myitemize}

    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
#>Set the job submission method for this task, overriding the suite default. This
#>determines how cylc job scripts are executed when a task is
#>ready to run. See Section~\ref{JobSubmissionMethods}.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} 
#>   \begin{myitemize}
#>       \item \lstinline=background= - direct subshell execution in the background 
#>       \item \lstinline=at_now= - the rudimentary Unix `at' scheduler
#>       \item \lstinline=loadleveler= - loadleveler generic
#>       \item \lstinline=ll_ecox= - loadleveler, NIWA EcoConnect environment
#>       \item \lstinline=ll_raw= - loadleveler for prepared script
#>   \end{myitemize}
#>\item {\em default:} \lstinline=background=
#>\end{myitemize}

    job submission log directory = string( default=None )
#>Set a job submission log directory for this task, overriding the suite
#> default. This is for stdout and stderr logs for the job scripts submitted by
#> cylc when tasks are ready to run.
#> For monolithic tasks (which don't resubmit sub-jobs themselves) these will
#> be the complete job logs for the task.  For owned tasks, the suite
#> owner's home directory will be replaced by the task owner's.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} None (see global default)
#>\end{myitemize}

    pre-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em before} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes before the 
#> ``task started'' message so an abort here will not register as a task
#> failure - it will appear that the task is stuck in the submitted state.
#> If global pre-command scripting is also defined, it will be executed
#> first.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} empty
#>\end{myitemize}

    post-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em after} the task command. If 
#> used at all, this scripting should be simple and reliable (anything
#> complex should go in the task itself) - it executes after the 
#> ``task finished'' message so an abort here will not register as a task
#> failure - it will appear that the task finished successfully.
#> If global post-command scripting is also defined, it will be executed
#> first.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} empty
#>\end{myitemize}

    owner = string( default=None )
#> If a task has a defined owner, cylc will attempt to execute the task
#> as that user, according to the global {\em owned task execution method}.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid username on the task host
#>\item {\em default:} None
#>\end{myitemize}

    host = string( default=None )
#> If a task has a defined host, cylc will attempt to execute the task on 
#> that remote host using passwordless ssh. The relevant suite
#> task scripts and executables, and cylc itself, must be installed on the 
#> remote host. The environment variables \lstinline=$CYLC_SUITE_DIR=
#> and \lstinline=$CYLC_DIR= must be overridden with their remote values. 
#> An {\em owner} must be defined if the task owner's username on the
#> remote host is not the same as the local suite owner's. Passwordless
#> ssh must be configured between the local suite owner and the remote
#> task owner.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid hostname on your network
#>\item {\em default:} None
#>\end{myitemize}

#>IGNORE
    task submitted hook = string( default=None )
    task submission failed hook = string( default=None )
    task started hook = string( default=None )
    task finished hook = string( default=None )
    task failed hook = string( default=None )
    task warning hook = string( default=None )
    task timeout hook = string( default=None )
#>RESUME

#> \paragraph{    task EVENT hooks \newline}
#>
#> Task event hooks facilitate centralized alerting for critical events
#> in operational suites. You can name script(s) to attach to various 
#> events using one or more of the following items:
#>\begin{myitemize}
#>\item {\bf task submitted hook}
#>\item {\bf task submission failed hook}
#>\item {\bf task started hook}
#>\item {\bf task finished hook}
#>\item {\bf task failed hook}
#>\item {\bf task timeout hook}
#>\end{myitemize}
#> These are task-specific settings; you can also set global defaults.
#> Hook scripts are called with the following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [EVENT] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where MESSAGE will describe what has happened.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} None
#>\end{myitemize}

#>IGNORE
    task submission timeout minutes = float( default=None )
    task execution timeout minutes = float( default=None )
#>RESUME

#> \paragraph{    task ACTION timeout minutes \newline}
#> 
#> You can set timeout intervals for submission' or execution with
#>the following items:
#>\begin{myitemize}
#>\item {\bf task submission timeout minutes}
#>\item {\bf task execution timeout minutes}
#>\end{myitemize}
#> If a task has not started (or finished) N minutes after it was submitted 
#> (or started), the task timeout hook script will be called with the
#> following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [ACTION] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where ACTION is `submission' or `execution'.
#> As for the hook scripts, these are task-specific settings; you can also
#> set global defaults.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} float (minutes)
#>\item {\em default:} None
#>\end{myitemize}

    reset execution timeout on incoming messages = boolean( default=True )
#> If True, and you have set an execution timeout, the timer will 
#> reset to zero every time a message is received from a running task.
#> Otherwise, the task will timeout if it does not finish in time,
#> even if it last sent a message (and was therefore still alive) 
#> within the initial timeout interval.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\end{myitemize}

    extra log files = force_list( default=list())
#> Any files named here will be added to the list of task logs
#> (stdout and stderr) viewable at run time via gcylc. The intention is 
#> to make easily accessible any output from tasks that resubmit
#> sub-jobs at run time (i.e.\ they don't remain under the control
#> of the job script initially submitted by cylc).
#> {\em WARNING: this feature is not well tested.} 
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} list of strings
#>\item {\em legal values:} valid file paths, may contain environment variables
#>\item {\em default:} empty
#>\end{myitemize}

#>IGNORE
# TO DO: This awaits a [tasks][[TASK]][[[prerequisites]]] section.
    hours = force_list( default=list())
#> Valid hours for this task - normally
#> determined by the suite dependency graph. {\em This item
#> should only be used for tasks that do not appear in the dependency graph.}
#> The reason for the existence of this item is: it allows you to define 
#> a task that is not used at startup (because it is not in the graph)
#> but can still be inserted into the suite manually later on 
#> (but note that \lstinline=cylc submit= can be used without defining 
#> valid hours - it will assume that the requested cycle time is valid 
#> for the task). {\em WARNING: currently you can't define dependencies
#> for a task outside of the graph - just need to implement a 
#> [[[prerequisites]]] section to allow this.}
#>\begin{myitemize} #>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} list of integers
#>\item {\em legal values:} $ 0,1,2,...,23$
#>\item {\em default:} empty
#>\end{myitemize}
#>RESUME

        [[[environment]]]
#> Use this section to define the task-specific task execution
#> environment. Variables defined here may refer to variables in
#> the global environment. Order of definition is preserved. See ``Task
#> Execution Environment'', Section~\ref{TaskExecutionEnvironment} for
#> more information.
        __many__ = string
#> Repeat for as many variables as you need.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[environment]]]
#>\item {\em type:} string
#>\item {\em legal values:} any valid environment variable assignment
#> expression. Whitespace around the `$=$' is fine (the
#> \lstinline=suite.rc= file is not a shell script). 
#> E.g. for the bash shell: 
#>   \begin{myitemize}
#>       \item \lstinline@FOO = $HOME/bar/baz@
#>       \item \lstinline@BAR = ${FOO}$GLOBALVAR@
#>       \item \lstinline@BAZ = $(echo "hello world")@
#>       \item \lstinline@WAZ = ${FOO%.jpg}.png@
#>   \end{myitemize}
#>\item {\em default:} None
#>\end{myitemize}

        [[[directives]]]
#> Use this section to define task-specific batch queue
#> scheduler `directives' (for {\em loadleveler} or {\em torque}, etc.).
#> These end up near the top of the job script cylc submits when the
#> task is ready to run. Whether or not items defined here are used
#> depends on the task's job submission method. The job
#> submission method should also define the directive comment prefix
#> (`\lstinline=# @=' for loadleveler) and final directive ('\lstinline=# @ queue=').
        __many__ = string
#> Repeat for as many directives as you need.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[directives]]]
#>\item {\em type:} string
#>\item {\em legal values:} any legal directive for your batch scheduler
#>\item {\em default:} None
#>\end{myitemize}

          [[[outputs]]]
        __many__ = string
#>\begin{myitemize}
#>\item {\em section:} 
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

[dummy mode]
#> Configure dummy mode behavior; used only if a suite runs in dummy mode.
clock offset from initial cycle time in hours = integer( default=24 )
#> Specify a clock offset of 0 to simulate real time operation, greater 
#> than zero to simulate catch up and transition to real time operation.
#>\begin{myitemize}
#>\item {\em section:} [dummy mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $>=0$
#>\item {\em default:} 24
#>\end{myitemize}

clock rate in seconds per dummy hour = integer( default=10 )
#> This determines the speed at which dummy mode suites run. A value
#> of 10, for example, means it will take 10 dummy seconds to simulate
#> one hour of real time operation.
#>\begin{myitemize}
#>\item {\em section:} [dummy mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $>= 0$
#>\item {\em default:} 10
#>\end{myitemize}

# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
#> Set the approximate number of dummy seconds that a dummy task
#> takes to execute.
#>\begin{myitemize}
#>\item {\em section:} [dummy mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $>=0$
#>\item {\em default:} 10
#>\end{myitemize}

job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
#>\begin{myitemize}
#>\item {\em section:}  [dummy mode]
#>\item {\em type:}
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
#>\item {\em section:} [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

# absolute, or relative to $CYLC_SUITE_DIR for portability
run time graph directory = string( default='$CYLC_SUITE_DIR/graphing')
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

run time graph filename  = string( default='runtime.dot')
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

# TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS
show family members = boolean( default=False )
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

use node color for edges = boolean( default=True )
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=ellipse'))
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

default edge attributes = force_list( default=list('color=black'))
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}


[[node groups]]
    __many__ = force_list( default=list())
#>\begin{myitemize}
#>\item {\em section:}  [visualization][[node groups]]
#>\item {\em type:}
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
#>\item {\em section:} [visualization][[node attributes]]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

[task insertion groups]
 __many__ = force_list()
#>\begin{myitemize}
#>\item {\em section:} [task insertion groups]
#>\item {\em type:}
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
#>\item {\em section:} [experimental]
#>\item {\em type:}
#>\item {\em legal values:}
#>   \begin{myitemize}
#>       \item 
#>   \end{myitemize}
#>\item {\em default:}
#>\end{myitemize}

