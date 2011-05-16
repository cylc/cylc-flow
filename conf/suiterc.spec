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
#>       \item \lstinline=loadleveler= - loadleveler, generic
#>       \item \lstinline=ll_ecox= - loadleveler, customized for
#>                    EcoConnect triplicate environment at NIWA
#>       \item \lstinline=ll_raw= - loadleveler, for existing job scripts
#>   \end{myitemize}
#>\item {\em default:} \lstinline=background=
#>\item {\em task override:} yes
#>\end{myitemize}

use lockserver = boolean( default=True )
#>Use of the cylc lockserver prevents
#> invocation of multiple instances of the same
#> suite at the same time, or invocation of a task (using
#> \lstinline=cylc submit=) if the same task is already running (in its
#> suite or by \lstinline=cylc submit=). It will only allow multiple
#> instances of a suite to run under
#> different registrations if the suite declares itself
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
#> Any task listed here will be excluded from the initial task pool 
#> (this goes for restarts too). If an {\em inclusion} list is also
#> specified, the initial pool will contain only included tasks
#> that have not been excluded. Excluded tasks can still be inserted at
#> run time. Other tasks may still depend on excluded tasks if they
#> have not been removed from the suite dependency graph (in which case
#> some manual triggering may be required).
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} list of task names
#>\item {\em default:} empty
#>\end{myitemize}

tasks to include at startup = force_list( default=list() )
#> If this list is not empty, any task NOT listed in it will be
#> excluded from the initial task pool (this goes for restarts too). If
#> an {\em exclusion} list is also specified, the initial pool will
#> contain only included tasks that have not been excluded. Excluded
#> tasks can still be inserted at run time. Other tasks may still depend
#> on excluded tasks if they have not been removed from the suite
#> dependency graph (in which case some manual triggering may be required).
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} list of task names
#>\item {\em default:} empty
#>\end{myitemize}

runahead limit in hours = integer( min=0, default=24 )
#>This is the maximum difference (in cycle time)
#>that cylc allows between the fastest and slowest tasks in the suite.
#>Cycling tasks with no prerequisites (most suites will not have any 
#>of these) will rapidly spawn ahead to the runahead limit. 
#> Clock-triggered tasks with no other prerequisites (most suites will
#> have some of these) will do the same if sufficiently far behind
#> the real time clock.
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
#>Roll the suite's cylc log archive (i.e.\ relabel ordered backups
#> and start the main file anew), every time the suite is started or
#> restarted.
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
task submitted hook script = string( default=None )
task submission failed hook script = string( default=None )
task started hook script = string( default=None )
task finished hook script = string( default=None )
task failed hook script = string( default=None )
task warning hook script = string( default=None )
task timeout hook script = string( default=None )
#>RESUME

#> \subsubsection{task EVENT hook scripts}
#> Task event hooks facilitate centralized alerting for critical events
#> in operational suites. You can name script(s) to attach to various 
#> events using one or more of the following items:
#>\begin{myitemize}
#>\item {\bf task submitted hook script}
#>\item {\bf task submission failed hook script}
#>\item {\bf task started hook script}
#>\item {\bf task finished hook script}
#>\item {\bf task failed hook script}
#>\item {\bf task timeout hook script}
#>\end{myitemize}
#> These items set global defaults that can be overridden by specific
#> tasks; or you can omit the defaults and just handle alerts for
#> certain critical tasks.
#> Hook scripts are called with the following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [EVENT] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where MESSAGE describes what has happened, and EVENT is the same 
#> as in the item name except that `submission failed' becomes 
#> `submit\_failed'.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} None
#>\item {\em task override:} yes
#>\end{myitemize}

#>IGNORE
task submission timeout in minutes = float( default=None )
task execution timeout in minutes = float( default=None )
#>RESUME

#> \subsubsection{task EVENT timeout in minutes}
#>You can set timeout intervals for task submission or execution with
#>the following items:
#>\begin{myitemize}
#>\item {\bf task submission timeout in minutes}
#>\item {\bf task execution timeout in minutes}
#>\end{myitemize}
#> If a task has not started (or finished) N minutes after it was submitted 
#> (or started), the task timeout hook script will be called with the
#> following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [EVENT] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where EVENT is `submission' or `execution'.
#> Like the hook scripts themselves, these global settings
#> can be overridden by specific tasks.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} float (minutes)
#>\item {\em default:} None
#>\item {\em task override:} yes
#>\end{myitemize}

reset execution timeout on incoming messages = boolean( default=True )
#> If True, and you have set an execution timeout, the timer will 
#> reset to zero every time a message is received from a running task.
#> Otherwise, the task will timeout if it does not finish in time,
#> even if it last sent a message (and was therefore still alive) 
#> within the timeout interval.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em task override:} yes
#>\end{myitemize}

pre-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> before the task command, for every task. If 
#> used, this scripting should be simple and reliable (anything
#> complex should go in the task itself) because it executes before the 
#> ``task started'' message (thus an error here will not register as a task
#> failure - it will appear that the task is stuck in the submitted state).
#> If task-specific pre-command scripting is also defined for particular
#> tasks, the global scripting will be executed first.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} multiline string
#>\item {\em default:} empty
#>\end{myitemize}

post-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em after} the task command. If 
#> used, this scripting should be simple and reliable (anything
#> complex should go in the task itself) because it executes after the 
#> ``task finished'' message (thus an error here will not register as a task
#> failure - it will appear that the task finished successfully).
#> If task-specific post-command scripting is also defined for particular
#> tasks, the global scripting will be executed first.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} multiline string
#>\item {\em default:} empty
#>\item {\em task override:} yes
#>\end{myitemize}

owned task execution method = option( sudo, ssh, default=sudo )
#>This specifies the means by which the chosen job submission method is
#> invoked for tasks that are owned by a user other than the suite
#> owner.\footnote{Why would you want to do this? At NIWA, parts of our complex
#> multi-model operational suite are deployed into, and run from, role
#> accounts that (at least in the development and test environments)
#> are managed by the experts on the associated scientific model or
#> subsystem.}  
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:}
#>   \begin{myitemize}
#>        \item sudo
#>        \item ssh
#>   \end{myitemize}
#>\item {\em default:} sudo
#>\end{myitemize}
#>To use sudo with loadleveler, for example, \lstinline=/etc/sudoers=
#> must be configured to allow the suite owner to execute the
#> \lstinline=llsubmit= command as the designated task owner.
#>To use ssh, passwordless ssh must be configured between the accounts
#> of the suite and task owners.

ignore task owners = boolean( default=False )
#>This item allows you to turn off the special treatment of owned tasks
#> (namely invocation of the task job submission method via sudo or ssh
#> as task owner), which can be useful when testing parts of a suite
#> containing owned tasks outside of its normal operational environment.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

use quick task elimination = boolean( default=True )
#>If this item is switch on (it is by default) cylc will remove spent
#> tasks from the suite sooner if they are known to have no downstream
#> dependents in subsequent forecast cycles. Otherwise only the generic
#> spent task elimination algorithm will be used.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\end{myitemize}

dummy mode only = boolean( default=False )
#>If True, cylc will abort cleanly if you try to run
#>the suite in real mode. This can be used for demo suites that
#>can't run for real because they've been copied out of their
#>normal operational environment.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

allow multiple simultaneous instances = boolean( default=False )
#>If True, the lockserver will allow multiple instances of this 
#> suite to run at the same time, so long as they are 
#> registered under different names. Use this if the I/O paths 
#> of every task in the suite are dynamically configured to be suite
#> specific (i.e.\ they must all contain the suite registration group
#> and name).
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
#>This specifies the shell used to interpret the temporary job
#> scripts submitted by cylc when a task is ready to run.
#> {\em It has no bearing on the shell you use to write task scripts.}
#> The pre- and post-command scripting items, if used, must be valid
#> for the job submission shell; this is entirely up to the user. The
#> suite environment sections must be converted similarly;
#> this is currently hardwired into cylc as 
#> \lstinline@export item=value@ (which works for both bash and ksh
#> because \lstinline=value= is entirely user-defined) so cylc would
#> have to be modified slightly if other shells are needed (this
#> probably not necessary as the scripting items should not be heavily
#> used anyway - see the warnings in the documentation for those items).
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
#> This section is used to identify any tasks with special behaviour.
#> The default task type does this:,
#> \begin{myitemize}
#> \item it starts running as soon as its prerequisites are satisfied
#> \item it spawns a successor (at the next valid cycle time for the
#>       particular task) as soon as its enters the running 
#> state\footnote{Spawning any earlier than this would
#> brings no advantage in terms of functional parallelism.}
#> \end{myitemize}
    clock-triggered = force_list( default=list())
#> Clock-triggered tasks wait on a wall clock time specified
#> as an offset {\em in hours} relative to their own cycle time, in
#> addition to any dependence they have on other tasks. Generally
#> speaking, only tasks that wait on external real time data need to be
#> clock-triggered.
#>\begin{myitemize}
#>\item {\em section:}  [special tasks]
#>\item {\em type:} list of tasknames followed by parenthesized offsets, in hours
#>\item {\em example:} foo(1.5), bar(2.25)
#>\item {\em default:} None
#>\end{myitemize}

    startup = force_list( default=list())
#> Startup tasks are oneoff tasks that are only used when {\em cold
#> starting a suite}, i.e.\ when starting up without assuming any previous
#> cycle. A startup task can be used to clean out or prepare a suite
#> workspace, for example, before other tasks run. Note that {\em cold
#> start tasks} (next item, below) are quite different beasts. 
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

    coldstart = force_list( default=list())
#> A coldstart task (or possibly a sequence of them) is used to satisfy
#> the dependence of an associated task with the same cycle time, on 
#> outputs from a previous cycle - when those outputs are not
#> available. The primary use for this is to cold start a warm-cycled
#> forecast model that normally depends on restart files (e.g.\ 
#> model background fields) generated by its previous forecast, in
#> circumstances whereby there is no previous forecast. 
#> This is required when cold starting the suite as a whole, but cold
#> start tasks can also be inserted into a running suite to restart a
#> model, for example, that has had to skip some cycles after running
#> into a serious problem (e.g.\ critical inputs not available).
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

    sequential = force_list( default=list())
#> By default, cylc tasks spawn a successor at the instant they start
#> running, so that successive instances of the same task can run in
#> parallel if the opportunity arises. {\em Sequential tasks}, however,
#> will not spawn a successor until they have finished running. This
#> should be used for (a) {\em tasks that cannot run in parallel with
#> their own previous instances} because they would somehow interfere with each
#> other (use cycle time in all I/O paths to avoid this); and (b)
#> {\em Warm cycled forecast models that write out restart files for
#> multiple cycles ahead} (except: see ``models with explicit restart
#> outputs'' below).\footnote{This is because you don't want Model(T)
#> waiting around to trigger off Model(T-12) if Model(T-6) has not
#> finished yet. If Model is forced to be sequential this can't happen
#> because Model(T) won't exist in the suite until Model(T-6) has
#> finished. But if Model(T-6) fails, it can be spawned-and-removed from
#> the suite so that Model(T) can then trigger off Model(T-12) - if it's
#> restart prerequisites allow that.} 
#>\begin{myitemize}
#>\item {\em section:}  [special tasks]
#>\item {\em type:} list of task names
#>\item {\em legal values:}
#>\item {\em default:} empty list
#>\end{myitemize}

    oneoff = force_list( default=list())
#> Oneoff tasks do not spawn a successor. After finishing, and once
#> they're no longer required to satisfy the prerequisites of others,
#> they are removed from the suite.  {\em Startup} and {\em
#> coldstart} tasks are automatically oneoff tasks and do not need
#> to be listed here.
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

    models with explicit restart outputs = force_list( default=list())
# TO DO: THESE TASKS COULD BE IDENTIFIED FROM THE GRAPH?

#> {\em This is only required in the unlikely event that you want a warm
#> cycled forecast model to be able to start at the instant its restart
#> files are ready (if other prerequisites are satisfied) {\bf before
#> its previous instance has finished}.}  If so, the task has to depend
#> on a special output message emitted by the previous instance as soon as
#> its restart files are ready, instead of just on the previous instance
#> finishing. {\em Tasks in this category must define their restart
#> output messages, {\bf which must contain the word ``restart''}}, in
#> [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[outputs]]] - see
#> Section~\ref{outputs}.
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\end{myitemize}

[task families]
#> A task family is a named group of tasks that appears as a single task
#> in the suite dependency graph. Thus the entire family triggers as a group,
#> and downstream tasks can trigger off the entire family finishing. 
#> Task families can have internal dependencies, and family members
#> can also appear in the graph as non-family tasks, although you're not
#> likely to need either of these features.
    __many__ = force_list( default=None )
#> Repeat MANY (task family name) to list each task family by name.
#>\begin{myitemize}
#>\item {\em section:} [task families]
#>\item {\em type:} list of task names (the family members)
#>\item {\em example:} ObsProc = ObsSurface, ObsSonde, ObsAircraft, ObsSat
#>\item {\em default:} None
#>\end{myitemize}

[dependencies]
#> This is where to define the suite dependency graph.
    [[__many__]]
#> Repeat MANY (list of hours for which the following chunk
#> of dependency graph is valid) as required for differing 
#> dependencies at different hours.
#>\begin{myitemize}
#>\item {\em section:} [dependencies]
#>\item {\em type:} list of integer hour
#>\item {\em legal values:} $0 \leq hour \leq 23$
#>\item {\em example:} [[0,6,12,18]]
#>\item {\em default:} None
#>\end{myitemize}

    graph = string
#> Define the dependency graph that is valid for specified list of hours.
#> You can use the \lstinline=cylc graph= command, or the gcylc
#> ``Graph'' right-click menu item, to plot the dependency graph as you
#> work on it.
#> See Section~\ref{DependencyGraph} for details.
#>\begin{myitemize}
#>\item {\em section:} [dependencies] $\rightarrow$ [[HOURS]]
#>\item {\em type:} multiline string
#>\item {\em legal values:} {\em refer to section~\ref{DependencyGraph}}
#>\item {\em example:}
#>  \begin{lstlisting}
#>graph = """
#>   foo => bar => baz & waz   # baz and waz both trigger off bar
#>   baz:out1 => faz           # faz triggers off an internal output of baz
#>   ColdFoo | foo(T-6) => foo # cold start or restart for foo
#>   X:fail => Y               # Y triggers if X fails
#>   X | X:fail => Z           # Z triggers if X finishes or fails
#>   """
#>  \end{lstlisting}
#>\item {\em default:} None
#>\end{myitemize}

[environment]
#> Use this section to define the global task execution environment, i.e.\
#> variables made available to all tasks. Order of definition 
#> is preserved. See Section~\ref{TaskExecutionEnvironment}, Task
#> Execution Environment, for more information.
__many__ = string
#> Repeat MANY (environment variable definition) for any environment
#> variables you need.
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
#> Repeat MANY (batch queue scheduler directive) for any directives
#> you need, e.g.:
#> \begin{lstlisting}
#>    class = parallel
#> \end{lstlisting}
#>\begin{myitemize}
#>\item {\em section:} [directives]
#>\item {\em type:} string
#>\item {\em legal values:} any legal directive for your batch scheduler
#>\item {\em default:} None
#>\end{myitemize}

[tasks]
    [[__many__]]
#> Repeat MANY (task name) for every task in the suite.

    description = string( default="No description supplied" )
#> Describe what this task does. The description can be retrieved at run time
#> by the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} No description supplied
#>\end{myitemize}

    command = force_list( default=list( cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
#> The commandline, or {\em list of commandlines}, to execute when
#> the task is ready to run. If the command is omitted or commented out
#> the task will run as a dummy task. If a list of commandlines is
#> supplied, the task will automatically resubmit with the second
#> commandline if the first fails (and so on).
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} \lstinline=cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP"=
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
#>       \item \lstinline=loadleveler= - loadleveler, generic
#>       \item \lstinline=ll_ecox= - loadleveler, customized for
#>                    EcoConnect triplicate environment at NIWA
#>       \item \lstinline=ll_raw= - loadleveler, for existing job scripts
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
#> immediately before the task command. If 
#> used, this scripting should be simple and reliable (anything
#> complex should go in the task itself) because it executes before the 
#> ``task started'' message (thus an abort here will not register as a task
#> failure - it will appear that the task is stuck in the submitted state).
#> If global pre-command scripting is also defined, it will be executed
#> first.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} multiline string
#>\item {\em default:} empty
#>\end{myitemize}

    post-command scripting = string( default='' )
#> Verbatim scripting to be executed, in the task execution environment,
#> immediately {\em after} the task command. If 
#> used, this scripting should be simple and reliable (anything
#> complex should go in the task itself) because it executes after the 
#> ``task finished'' message (thus an abort here will not register as a task
#> failure - it will appear that the task finished successfully).
#> If global post-command scripting is also defined, it will be executed
#> first.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} multiline string
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
#> If a task specifies a remote host, cylc will attempt to execute the
#> task on that host, using the specified job submission method, by
#> passwordless ssh. The relevant suite
#> task scripts and executables, and cylc itself, must be installed on the 
#> remote host. The environment variables \lstinline=$CYLC_SUITE_DIR=
#> and \lstinline=$CYLC_DIR= must be overridden with their remote values. 
#> An {\em owner} must be defined if the task owner's username on the
#> remote host is not the same as the local suite owner's. Passwordless
#> ssh must be configured between the local suite owner and remote
#> task owner accounts.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid hostname on your network
#>\item {\em default:} None
#>\end{myitemize}

#>IGNORE
    task submitted hook script = string( default=None )
    task submission failed hook script = string( default=None )
    task started hook script = string( default=None )
    task finished hook script = string( default=None )
    task failed hook script = string( default=None )
    task warning hook script = string( default=None )
    task timeout hook script = string( default=None )
#>RESUME

#> \paragraph{    task EVENT hook scripts}
#>
#> Task event hooks facilitate centralized alerting for critical events
#> in operational suites. You can name script(s) to attach to various 
#> events using one or more of the following items:
#>\begin{myitemize}
#>\item {\bf task submitted hook script}
#>\item {\bf task submission failed hook script}
#>\item {\bf task started hook script}
#>\item {\bf task finished hook script}
#>\item {\bf task failed hook script}
#>\item {\bf task timeout hook script}
#>\end{myitemize}
#> These are task-specific settings; you can also set global defaults.
#> Hook scripts are called with the following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> EVENT TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where MESSAGE describes what has happened, and EVENT is the same 
#> as in the item name except that `submission failed' becomes 
#> `submit\_failed'.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} None
#>\end{myitemize}

#>IGNORE
    task submission timeout in minutes = float( default=None )
    task execution timeout in minutes = float( default=None )
#>RESUME

#> \paragraph{    task EVENT timeout in minutes}
#> 
#> You can set timeout intervals for task submission or execution with
#>the following items:
#>\begin{myitemize}
#>\item {\bf task submission timeout in minutes}
#>\item {\bf task execution timeout in minutes}
#>\end{myitemize}
#> If a task has not started (or finished) N minutes after it was submitted 
#> (or started), the task timeout hook script will be called with the
#> following arguments supplied by cylc:
#> \begin{lstlisting}
#> <script> [EVENT] TASK CYCLE_TIME MESSAGE
#> \end{lstlisting}
#> where EVENT is `submission' or `execution'.
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
#> within the timeout interval.
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
#> Repeat MANY (environment variable definition) for any 
#> task-specific environment variables you need.
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
#> scheduler `directives' (for loadleveler, or torque, etc.).
#> These end up near the top of the job script cylc submits when the
#> task is ready to run. Whether or not items defined here are used
#> depends on the task's job submission method. The job
#> submission method should also define the directive comment prefix
#> (`\lstinline=# @=' for loadleveler) and final directive (`\lstinline=# @ queue=').
        __many__ = string
#> Repeat MANY (batch queue scheduler directive) for any directives 
#> you need.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[directives]]]
#>\item {\em type:} string
#>\item {\em legal values:} any legal directive for your batch scheduler
#>\item {\em default:} None
#>\item {\em example:} \lstinline@class = parallel@
#>\end{myitemize}

        [[[outputs]]]
#> \label{outputs}
#> {\em This section is only required if other tasks 
#> trigger off specific labeled outputs of this task} (as opposed to 
#> triggering off it finishing). Tasks with explicit outputs 
#> would generally do their own cylc messaging so that they can report
#> said outputs complete as soon as they are ready (the cylc
#> task wrapper does report such explicit outputs complete when the task
#> finishes, but then you might as well not bother with explicit outputs
#> and just trigger off the task finishing).
        __many__ = string
#> Repeast MANY (output message definition) for any explicit output
#> messages emitted by this task.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[outputs]]]
#>\item {\em type:} string
#>\item {\em legal values:} a message containing
#>           \lstinline=$(CYCLE_TIME)=, possibly with an offset as shown
#> below. {\bf Note the round parentheses in \lstinline=$(CYCLE_TIME)=} 
#> - the \lstinline=suite.rc= file is not a shell script.
#>\item {\em default:} None
#>\item{ \em examples:}
#> \begin{lstlisting}
#> foo = "sea state products ready for $(CYCLE_TIME)"
#> r6  = "nwp restart files ready for $(CYCLE_TIME+6)"
#> r12 = "nwp restart files ready for $(CYCLE_TIME+12)"
#> \end{lstlisting}
#> where the item name must match the output label associated with this task
#> in the suite dependency graph, e.g.:
#> \begin{lstlisting}
#> [dependencies]
#>    [[6,18]]
#>        graph = TaskA:foo => TaskB
#> \end{lstlisting}
#>\end{myitemize}

[dummy mode]
#> Configure dummy mode behavior (used only you run the suite in dummy mode).
clock offset from initial cycle time in hours = integer( default=24 )
#> Specify a clock offset of 0 to simulate real time operation, greater 
#> than zero to simulate catch up and transition to real time operation.
#>\begin{myitemize}
#>\item {\em section:} [dummy mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $\geq 0$
#>\item {\em default:} 24
#>\end{myitemize}

clock rate in seconds per dummy hour = integer( default=10 )
#> This determines the speed at which dummy mode suites run. A value
#> of 10, for example, means it will take 10 dummy seconds to simulate
#> one hour of real time operation.
#>\begin{myitemize}
#>\item {\em section:} [dummy mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $\geq 0$
#>\item {\em default:} 10
#>\end{myitemize}

# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
#> Set the approximate number of dummy seconds that a dummy task
#> takes to execute.
#>\begin{myitemize}
#>\item {\em section:} [dummy mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $\geq 0$
#>\item {\em default:} 10
#>\end{myitemize}

#>IGNORE
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
#> For testing purposes you can also choose to have dummy tasks executed
#> job submission methods (you are unlikely to need this).
#>\begin{myitemize}
#>\item {\em section:}  [dummy mode]
#>\item {\em type:} string
#>\item {\em legal values:} 
#>   \begin{myitemize}
#>       \item \lstinline=background= - direct subshell execution in the background 
#>       \item \lstinline=at_now= - the rudimentary Unix `at' scheduler
#>       \item \lstinline=loadleveler= - loadleveler, generic
#>       \item \lstinline=ll_ecox= - loadleveler, customized for
#>                    EcoConnect triplicate environment at NIWA
#>       \item \lstinline=ll_raw= - loadleveler, for existing job scripts
#>   \end{myitemize}
#>\item {\em default:} \lstinline=background=
#>\item {\em task override:} yes
#>\end{myitemize}
#>RESUME

[visualization]
#> The settings in this setting affect \lstinline=suite.rc= graph plotting
#> (via \lstinline=cylc graph= or gcylc) and the run time resolved
#> dependency graph generated at the start of each suite run. They do not
#> affect the graph suite control interface.
run time graph cutoff in hours = integer( default=24 )
#> Cylc generates a run time graph of resolved dependencies, from the
#> start of every run until each task has passed this cutoff. Use 
#> dummy mode to generate run time graphs quickly.
#>\begin{myitemize}
#>\item {\em section:} [visualization]
#>\item {\em type:} integer
#>\item {\em legal values:} $>=0$
#>\item {\em default:} 24
#>\end{myitemize}

run time graph directory = string( default='$CYLC_SUITE_DIR/graphing')
#> Where to put the run time graph file, called \lstinline=runtime-graph.dot=.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} string
#>\item {\em legal values:} a valid local file path
#>\item {\em default:} \lstinline=$CYLC_SUITE_DIR/graphing=
#>\end{myitemize}

show family members = boolean( default=False )
# TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS?
#> This item specifies whether to plot members tasks of a family, or the group
#> as a whole. 
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

use node color for edges = boolean( default=True )
#> Outgoing graph edges can be plotted in the same color as the
#> parent node, which makes it easier to follow a path through a complex
#> graph. 
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\end{myitemize}

default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=box'))
#> Set the default attributes (color and style etc.) of task nodes.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} list of {\em quoted} \lstinline@'attribute=value'@ pairs
#>\item {\em legal values:} see graphviz or pygraphviz documentation
#>\item {\em default:} \lstinline@'style=unfilled', 'color=black', 'shape=ellipse'@
#>\end{myitemize}

default edge attributes = force_list( default=list('color=black'))
#> Set the default attributes (color and style etc.) of graph edges.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} list of graph edge attributes
#>\item {\em legal values:} see graphviz or pygraphviz documentation
#>\item {\em default:} \lstinline@'color=black'@
#>\end{myitemize}

[[node groups]]
#> Define named groups of graph nodes (tasks) that can have
#> attributes assigned to them in the [[node attributes]] section.
    __many__ = force_list( default=list())
#> Repeat MANY for each node group.  The same task can appear in
#> multiple groups.
#>\begin{myitemize}
#>\item {\em section:}  [visualization] $\rightarrow$ [[node groups]]
#>\item {\em type:} list of task names
#>\item {\em default:} empty
#>\end{myitemize}

[[node attributes]]
#> Here you can assign graph node attributes to specific tasks or named
#> groups of tasks defined in the [[node groups]] section.
    __many__ = force_list( default=list())
#> Repeat MANY for any specific tasks or named groups that you want to 
#> assign attributes to.
#>\begin{myitemize}
#>\item {\em section:} [visualization] $\rightarrow$ [[node attributes]]
#>\item {\em type:} list of {\em quoted} \lstinline@'attribute=value'@ pairs
#>\item {\em legal values:} see graphviz or pygraphviz documentation
#>\item {\em default:} None
#>\end{myitemize}

[task insertion groups]
#> Define named groups of tasks that can be inserted into a suite en mass.
#> May be useful for groups of related cold start tasks, for instance.
 __many__ = force_list()
#> Repeat MANY for any task insertion groups you need.
#>\begin{myitemize}
#>\item {\em section:} [task insertion groups]
#>\item {\em type:} list of task names
#>\item {\em default:} None
#>\end{myitemize}

[cylc local environment]
#> Use this section to add variables to the environment in which cylc
#> itself is running. These variables will be available to processes
#> spawned directly by cylc itself, namely timeout and alert hook
#> scripts. {\em Do not use this section to alter the task execution
#> environment - use the plain [environment] sections for that - 
#> variables defined in this section will only be available 
#> to tasks if local direct job submission methods are used}. 
__many__ = string
#> Repeat MANY (environment variable definition) for any environment
#> variables you need.
#>\begin{myitemize}
#>\item {\em section:} [cylc local environment]
#>\item {\em type:} string
#>\item {\em legal values:} any valid environment variable assignment
#> expression. Whitespace around the `$=$' is fine (the
#> \lstinline=suite.rc= file is not a shell script). 
#> E.g. for the bash shell: 
#>   \begin{myitemize}
#>       \item \lstinline@FOO = $HOME/bar/baz@
#>       \item \lstinline@BAZ = $(echo "hello world")@
#>       \item \lstinline@WAZ = ${FOO%.jpg}.png@
#>   \end{myitemize}
#>\item {\em default:} None
#>\end{myitemize}

[experimental]
#> Section for experimenting with new configuration items
live graph movie = boolean( default=False )
#> Turning this item on will result in a new dot file being written out to the 
#> suite graphing directory every time the suite state changes. These
#> can later be converted into movie frames and animated with appropriate 
#> image processing tools.
#>\begin{myitemize}
#>\item {\em section:} [experimental]
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\end{myitemize}

