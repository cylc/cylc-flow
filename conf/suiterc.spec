#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

# THIS SPEC FILE DEFINES ALL LEGAL ENTRIES IN CYLC SUITE.RC FILES.
# LaTeX documentation is maintained below each item, in comments that
# are ignored during suite.rc parsing, but is and extracted during
# document processing (which strips off the leading '#>' characters). 
# ITEM DOCUMENTATION SHOULD BE UPDATED WHENEVER AN ITEM IS CHANGED.

#>\lstset{language=}

# NOTE: A CONFIGOBJ or VALIDATE BUG? LIST CONSTRUCTOR FAILS IF LAST LIST
# ELEMENT IS FOLLOWED BY A SPACE (OR DOES IT JUST NEED A TRAILING COMMA?):
#   GOOD:
# foo = string_list( default=list('foo','bar'))
#   BAD:
# bar = string_list( default=list('foo','bar' ))

#> \subsection{Include Files}
#> \label{IncludeFiles}
#> Include-files can be used to help organize the task definition
#> sections of large suites, or to group common environment variable settings
#> into one file that can be included in multiple task environment sections 
#> (instead of polluting the global namespace for {\em all} tasks).
#> Include-file boundaries are arbitrary (they can cross suite.rc 
#> section boundaries). They can be multiply included and nested.
#> \begin{lstlisting}
#>%include path/to/myfile.rc
#> \end{lstlisting}
#> Include-file paths should be specified portably\footnote{If the suite
#> is copied to another location you shouldn't have to change hardwired
#> paths.} relative to the suite definition directory.
#> The \lstinline=cylc edit= command can optionally provide an inlined 
#> version of a suite.rc file that is automatically split back into 
#> its constituent include-files when you save the file and exit the editor.

#>\subsection{Suite Level Items}

title = string( default="No title supplied" )
#>The suite title is displayed in the gcylc
#> suite database window, and can also be retrieved from a suite at run
#> time using the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} ``No title supplied''
#>\item {\em example:} \lstinline@title = "Suite Foo"@
#>\end{myitemize}

description = string( default="No description supplied" )
#>The suite description can be retrieved by 
#>gcylc right-click menu and the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} ``No description supplied''
#>\item {\em example:}
#> \begin{lstlisting}
#> description = """
#> Here's what this suite does ...
#> ... on a good day"""
#> \end{lstlisting}
#>\end{myitemize}

initial cycle time = integer( default=None )
#> Initial suite cycle time. At startup each cycling task will be 
#> inserted into the suite with this cycle time, or with the closest
#> subsequent valid cycle time for the task (unless excluded by the 
#> {\em tasks to include|exclude at startup} items; and note that
#> how cold start tasks are inserted, or not, depends on the 
#> start up method - cold, warm, or raw).
#> Alternatively you can provide, or override, the initial cycle 
#> time on the command line or suite start GUI panel.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} integer
#>\item {\em default:} None
#>\item {\em example:} \lstinline@initial cycle time = 2011052318@
#>\end{myitemize}

final cycle time = integer( default=None )
#> Final suite cycle time. Cycling tasks will be held (i.e.\ not 
#> allowed to spawn a successor) after passing this cycle time. When all
#> tasks have reached this time the suite
#> will shut down (unless it also contains still-running asynchronous
#> tasks).
#> Alternatively you can provide, or override, the final cycle 
#> time on the command line or suite start GUI panel.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} integer
#>\item {\em default:} None
#>\item {\em example:} \lstinline@final cycle time = 2011052318@
#>\end{myitemize}

job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=background )
#>The default job submission method for the suite. This
#>determines how cylc job scripts are executed when a task is
#>ready to run - see Section~\ref{TaskExecution}.
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
#>\item {\em example:} \lstinline@job submission method = at_now@
#>\end{myitemize}

job submission command template = string( default=None )
#> Set the command template for the job submission method.
#> The template should be suitable for substitution of the keys
#> {\em jobfile_path}, {\em stdout_file}, {\em stderr_file} in a dict.
#>\begin{myitemize}
#>\item {\em section:}  (top level)
#>\item {\em type:} string
#>\item {\em legal values:} a string template for a dict with keys
#> {\em jobfile_path}, {\em stdout_file}, {\em stderr_file}.
#>\item {\em default:} None (see suite level default)
#>\item {\em example:} \lstinline@llsubmit %(jobfile_path)s@
#>\end{myitemize}

use lockserver = boolean( default=False )
#> The cylc lockserver generalizes traditional {\em lock files} to the network.
#> It prevents prevents invocation of multiple instances of the same
#> suite at the same time, or invocation of a task (using
#> \lstinline=cylc submit=) if the same task is already running (in its
#> suite or by \lstinline=cylc submit=). It will allow multiple
#> instances of a suite to run under
#> different registrations {\em only if} the suite declares itself
#> capable of that (see \lstinline=suite.rc= item
#> ``allow multiple simultaneous instances'').
#> The lockserver cannot prevent you from running distinct {\em copies}
#> of a suite simultaneously. See \lstinline=cylc lockserver --help= for 
#> how to run the lockserver, and \lstinline=cylc lockclient --help= for 
#> occasional manual lock management requirements. The lockserver is 
#> currently disabled by default. 
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@use lockserver = True@
#>\end{myitemize}

remote host = string( default=None )
#> If a suite level remote host is specified cylc will attempt to run 
#> every task on that host, except for particular tasks that override
#> the host setting, by passwordless ssh. Use this if all of your tasks,
#> or at least the bulk of them, run on the same remote host, otherwise
#> define remote hosts at task level. The relevant suite task
#> scripts and executables,
#> and cylc itself, must be installed on the remote host. The items
#> {\em remote cylc directory} and {\em remote suite directory} must
#> also be specified at suite and/or task level, and {\em owner} must be
#> defined (at suite and/or task level) if the task owner's username on
#> the remote host is not the same as the local suite owner's.
#> Passwordless ssh must be configured between the local suite owner and
#> remote task owner accounts.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:} a valid hostname on your network
#>\item {\em default:} None
#>\item {\em example:} \lstinline@remote host = foo.niwa.co.nz@
#>\end{myitemize}

remote shell template = string( default=None )
#> A template of the remote shell command for a submitting a remote task.
#> The template should be suitable for substitution of the keys
#> {\em destination}, {\em jobfile_path} and {\em command} in a dict.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:} a string template for a dict with keys "destination", "jobfile_path" and "command"
#>\item {\em default:} None
#>\end{myitemize}

remote cylc directory = string( default=None )
#> For tasks that declare a remote host at suite level, this defines the
#> path to the remote cylc installation (i.e.\
#> \lstinline=$CYLC_DIR=). 
#> Use this if all of your tasks,
#> or at least the bulk of them, run on the same remote host, otherwise
#> define the remote cylc directory at task level. 
#> on the remote host.
#>\begin{myitemize}
#>\item {\em section:}  (top level)
#>\item {\em type:} string
#>\item {\em legal values:} a valid directory path on the remote host
#>\item {\em default:} None
#>\item {\em example:} \lstinline@remote cylc directory = /path/to/cylc/on/remote/host@
#>\end{myitemize}
#> This item is compulsory for remotely hosted tasks.

remote suite directory = string( default=None )
#> For tasks that declare a remote host at suite level, this 
#> specifies the path to the suite definition directory on the remote host,
#> in order to give remote tasks access to files stored there
#> (via \lstinline=$CYLC_SUITE_DIR=) and to the 
#> suite bin directory (via \lstinline=$PATH=).
#> Use this suite level item if all of your tasks,
#> or at least the bulk of them, run on the same remote host, otherwise
#> define the remote suite directory at task level. 
#>\begin{myitemize}
#>\item {\em section:}  (top level)
#>\item {\em type:} string
#>\item {\em legal values:} a valid directory path on the remote host
#>\item {\em default:} None
#>\item {\em example:} \lstinline@remote suite directory = /path/to/suite/on/remote/host@
#>\end{myitemize}
#> This item is not compulsory for remotely hosted tasks, because 
#> some tasks may not require access to files in the suite definition
#> directory.
 
owner = string( default=None )
#> If a task has a defined owner, cylc will attempt to execute the task
#> as that user, according to the suite level {\em owned task execution method}.
#> Use this if all of your tasks, or at least the bulk of them, run under
#> the same username, otherwise define task owners at task level (or 
#> not at all, if all tasks run as the suite owner, which is the usual
#> situation). 
#>\begin{myitemize}
#>\item {\em section:}  (top level)
#>\item {\em type:} string
#>\item {\em legal values:} a valid username on the task host
#>\item {\em default:} None
#>\item {\em example:} \lstinline@owner = bob@
#>\end{myitemize}

use secure passphrase = boolean( default=False )
#>If True, any intervention in a
#> running suite will require a special passphrase to be present, 
#> with secure permissions (as for ssh keys) in the file 
#> \lstinline=$HOME/.cylc/security/GROUP:NAME=.
#> The passphrase file must be present in
#> any user account that needs access to the suite (remotely hosted tasks
#> for instance). The passphrase itself is never transferred
#> across the network (a secure MD5 checksum is).  This guarantees
#> suite security so long as your user account isn't breached.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@use secure passphrase = True@
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
#>\item {\em example:} \lstinline@tasks to exclude at startup = TaskA, TaskB, TaskC@
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
#>\item {\em example:} \lstinline@tasks to include at startup = TaskA, TaskB, TaskC@
#>\end{myitemize}

runahead limit in hours = integer( min=0, default=24 )
#> If a task's cycle time is ahead of the oldest non-failed task in the
#> suite by more than this limit, it will be prevented from spawning a 
#> successor until the slowest tasks catch up sufficiently. Failed
#> tasks (which are not automatically removed from a suite) do not
#> activate the runahead limit (but downstream dependencies that can't 
#> run because of them will). 
#> In real time operation the runahead limit is of
#> little consequence because the suite will be constrained 
#> by its real time clock-triggered tasks (however, it must be long
#> enough to cover the range of tasks present in the suite; for example
#> a task that only runs once per day needs to spawn 24 hours ahead). 
#> The runahead limit is
#> intended to stop fast tasks from running off far into the future in
#> historical case studies. 
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} integer
#>\item {\em legal values:} $>= 0$
#>\item {\em default:} 24
#>\item {\em example:} \lstinline@runahead limit in hours = 48@
#>\end{myitemize}

suite log directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME/log/suite' )
#>Cylc logs all events to a suite log file. The main log and
#> its automatic backups are stored under this directory. {\em You must
#> ensure the directory is suite-specific; this can be done without hard wiring by
#> using suite identity environment variables as the default value does.}
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/CylcSuiteLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME=
#>\item {\em example:} \lstinline@suite log directory = $HOME/CSL/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME@
#>\end{myitemize}

roll log at startup = boolean( default=True )
#>Roll the cylc log for the suite (i.e.\ relabel ordered backups
#> and start the main log anew) when the suite is started or
#> restarted.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em example:} \lstinline@roll log at startup = False@
#>\end{myitemize}

state dump directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME/state' )
#> Suite state dump files allow cylc to restart suites from previous states. 
#> The default state dump and its backups, and special
#> pre-intervention state dumps are all stored under this directory.
#> {\em You must ensure the directory is suite-specific; this can be
#> done without hard wiring by using suite identity environment variables
#> as the default value does.}
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/CylcStateDumps/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME=
#>\item {\em example:} \lstinline@state dump directory = $HOME/CSD/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME@
#>\end{myitemize}

number of state dump backups = integer( min=1, default=10 )
#> Length, in  number of changes, of the automatic rolling
#> archive of state dump files that allows you to restart a suite from a
#> previous state. 
#> Every time a task changes state cylc updates the state dump and rolls
#> previous states back one on the archive. 
#> You'll probably only ever need the latest (most recent) state dump,
#> which is automatically used in a restart, but any previous state 
#> still in the archive can be used. {\em Additionally, special labeled 
#> state dumps that can also be used to restart the suite are written
#> out prior to actioning any suite intervention.}
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} integer
#>\item {\em legal values:} $>= 1$
#>\item {\em default:} 10
#>\item {\em example:} \lstinline@number of state dump backups = 20@
#>\end{myitemize}

job submission log directory = string( default='$HOME/cylc-run/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME/log/job' )
#> The directory in which to put the stdout and stderr
#> log files for the job scripts submitted by cylc when tasks are ready to run.
#> For monolithic tasks (which don't resubmit sub-jobs themselves) these will
#> be the complete job logs for the task.  For owned tasks, the suite
#> owner's home directory will be replaced by the task owner's.
#>\begin{myitemize}
#>\item {\em section:} (top level)  
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/CylcJobLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME=
#>\item {\em example:} \lstinline@job submission log directory = $HOME/Logs/$CYLC_SUITE@
#>\end{myitemize}
#> {\em For remotely hosted tasks this configuration item is currently ignored - task
#> output logs are written to the remote task owner's home directory.} (This will be
#> addressed in a future cylc release).

#>IGNORE
task submitted hook script = string( default=None )
task submission failed hook script = string( default=None )
task started hook script = string( default=None )
task succeeded hook script = string( default=None )
task failed hook script = string( default=None )
task warning hook script = string( default=None )
task timeout hook script = string( default=None )
#>RESUME

#> \subsubsection{task EVENT hook scripts}
#> Task event hooks facilitate centralized alerting for critical events.
#> The following hooks are available:
#>\begin{myitemize}
#>\item {\bf task submitted hook script}
#>\item {\bf task submission failed hook script}
#>\item {\bf task started hook script}
#>\item {\bf task succeeded hook script}
#>\item {\bf task failed hook script}
#>\item {\bf task warning hook script}
#>\item {\bf task timeout hook script}
#>\end{myitemize}
#> These suite level defaults can be overridden by specific tasks, or you
#> can omit the defaults and just attach hook scripts for critical tasks.
#> Cylc provides a hook script that sends emails: cylc email-alert.
#> Your own hook scripts can be located in suite bin directories. 
#> Hook scripts are passed the following arguments:
#> \begin{lstlisting}
#> <hook-script> EVENT SUITE TASKID MESSAGE
#> \end{lstlisting}
#> where MESSAGE describes what has happened; EVENT is 
#> either `submitted', `started', `succeeded', `failed', `timeout', 
#> or `submission\_failed'; and TASKID is the unique task identifier
#> (e.g.\ \lstinline=NAME%CYCLE_TIME= for cycling tasks).
#> Note that {\em hook scripts are called by cylc, not by tasks,} 
#> so if you wish to pass in additional information via the environment, 
#> use the [cylc local environment] section, not [environment].
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} string
#>\item {\em default:} None
#>\item {\em example:} \lstinline@task failed hook script = cylc email-alert@
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
#> If a task has not started (or finished) this number of minutes after
#> it was submitted (or started), the task timeout hook script will be
#> called by cylc with the following arguments:
#> \begin{lstlisting}
#> <script> EVENT SUITE TASKID MESSAGE
#> \end{lstlisting}
#> where message describes what has happened; EVENT is `submission' or
#> `execution'; and TASKID is the unique task identifier
#> (e.g.\ \lstinline=NAME%CYCLE_TIME= for cycling tasks).
#> Like the hook scripts themselves, these suite level settings
#> can be overridden by specific tasks.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} float (minutes)
#>\item {\em default:} None
#>\item {\em example:} \lstinline@task execution timeout in minutes = 10@
#>\end{myitemize}

reset execution timeout on incoming messages = boolean( default=True )
#> If True, and you have set an execution timeout, the timer will 
#> reset to zero every time a message is received from a running task.
#> Otherwise, the task will timeout if it does not finish in time,
#> even if it last sent a message (and was, by implication, still alive) 
#> within the timeout interval.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em example:} \lstinline@reset execution timeout on incoming messages = False@
#>\end{myitemize}

pre-command scripting = string( default='' )
#> Scripting to be executed verbatim in the task execution environment,
#> before the task command, for every task. 
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} multiline string
#>\item {\em default:} empty
#>\item {\em example:} 
#> \begin{lstlisting}
#>    pre-command scripting = """
#>      . $HOME/.profile
#>      echo Hello from suite $CYLC_SUITE!"""
#> \end{lstlisting}
#>\end{myitemize}

post-command scripting = string( default='' )
#> Scripting to be executed verbatim in the task execution environment,
#> immediately after the task command, for every task. 
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} multiline string
#>\item {\em default:} empty
#>\item {\em example:}
#> \begin{lstlisting}
#>    post-command scripting = """
#>      . $HOME/.profile
#>      echo Goodbye from suite $CYLC_SUITE!"""
#> \end{lstlisting}
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
#>\item {\em example:} \lstinline@owned task execution method = ssh@
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
#>\item {\em example:} \lstinline@ignore task owners = True@
#>\end{myitemize}

use quick task elimination = boolean( default=True )
#>If quick task elimination is switched on (it is by default) cylc will
#> remove spent
#> tasks from the suite sooner if they are known to have no downstream
#> dependents in subsequent forecast cycles. Otherwise the generic
#> spent task elimination algorithm will be used for all tasks. 
#> (Mainly used in cylc development).
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em example:} \lstinline@use quick task elimination = False@
#>\end{myitemize}

simulation mode only = boolean( default=False )
#>If True, cylc will abort cleanly if you try to run
#>the suite in real mode. This can be used for demo suites that
#>can't run in real mode because they've been copied out of their
#>normal operating environment.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@simulation mode only = True@
#>\end{myitemize}

allow multiple simultaneous instances = boolean( default=False )
#>If True, the lockserver will allow multiple instances of this 
#> suite to run at the same time under different registrations. You can
#> do this
#> if the I/O paths of every task in the suite are dynamically
#> configured to be suite specific (i.e.\ they all contain the
#> suite registration group and name).
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@allow multiple simultaneous instances = True@
#>\end{myitemize}

job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
#>\label{JobSubShell}
#>This is the shell used to interpret the job script submitted by cylc
#> when a task is ready to run.
#> {\em It has no bearing on the shell used in task implementations.}
#> Global pre- and post-command scripting, and the content of the task
#> commands themselves, must be valid in the job submission shell. The
#> suite environment sections must be converted similarly;
#> this is currently hardwired into cylc as 
#> \lstinline@export item=value@ (which works for both bash and ksh
#> because \lstinline=value= is entirely user-defined) so cylc would
#> have to be modified slightly if other shells are needed.
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
#>\item {\em example:} \lstinline@job submission shell = /bin/ksh@
#>\end{myitemize}

manual task completion messaging = boolean( default=False )
#> If a task's initiating process detaches and exits before task
#> processing is finished, then cylc cannot arrange for the task to
#> automatically signal when it has succeeded or failed. In such cases
#> you must insert some minimal cylc messaging in appropriate places in
#> the task implementation. Use this global setting in the unlikely
#> event that all, or most, of your tasks are in this category; otherwise
#> you can set it on a per task basis.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} \lstinline=False= 
#>\item {\em example:} \lstinline@manual task completion messaging = True@
#>\end{myitemize}

UTC mode = boolean( default=False )
#> By default cylc runs off the suite host's system clock. Set this
#> item True to run the suite in UTC even if the system clock is not in
#> UTC mode. Clock-triggered tasks will trigger when the
#> current UTC time reaches their own cycle time plus
#> offset; and other time values used, reported, or logged by cylc will
#> also be in UTC. 
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} \lstinline=False= 
#>\item {\em example:} \lstinline@UTC mode = True@
#>\end{myitemize}

[special tasks]
#> This section identifies any tasks with special behaviour.
#> By default tasks:
#> \begin{myitemize}
#> \item start running as soon as their prerequisites are satisfied
#> \item spawns a successor at its next valid cycle time as soon as it
#> enters the running state\footnote{Spawning any earlier than this 
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
#>\item {\em default:} None
#>\item {\em legal values:} The offset, in hours, can be positive or
#> negative.
#>\item {\em example:} \lstinline@clock-triggered = foo(1.5), bar(2.25)@
#>\end{myitemize}
#> Clock-triggered tasks currently can't be triggered manually prior to
#> their trigger time. This will change in a future cylc release. In
#> the meantime if you need to do this you can kill the task with
#> \lstinline=cylc remove=, run it manually outside of the suite with
#> \lstinline=cylc submit=, and then manually trigger any direct
#> downstream dependencies of the killed task. 

    startup = force_list( default=list())
#> Startup tasks are one off tasks that are only used when {\em cold
#> starting a suite}, i.e.\ when starting up without assuming any previous
#> cycle. A startup task can be used to clean out or prepare a suite
#> workspace, for example, before other tasks run. 
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\item {\em example:} \lstinline@startup = TaskA, TaskB@
#>\end{myitemize}

    cold start = force_list( default=list())
#> A cold start task (or possibly a sequence of them) is used to satisfy
#> the dependence of an associated task with the same cycle time, on 
#> outputs from a previous cycle - when those outputs are not
#> available. The primary use for this is to cold start a warm-cycled
#> forecast model that normally depends on restart files (e.g.\ 
#> model background fields) generated by its previous forecast, when
#> there is no previous forecast. 
#> This is required when cold starting the suite, but cold
#> start tasks can also be inserted into a running suite to restart a
#> model that has had to skip some cycles after running
#> into a serious problem (e.g.\ critical inputs not available).
#> Cold start tasks can invoke real cold start processing, or they
#> can just be dummy tasks (which don't specify a command) that
#> stand in for some external process that has to be completed before
#> the suite is started.
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\item {\em example:} \lstinline@cold start = ColdA, TaskF@
#>\end{myitemize}

    sequential = force_list( default=list())
#> By default, a cylc task spawns a successor when it starts running, so
#> that successive instances of the same task can run in
#> parallel if the opportunity arises (i.e.\ if their prerequisites 
#> happen to be satisfied before their predecessor has finished). {\em
#> Sequential tasks}, however,
#> will not spawn a successor until they have finished successfully. This
#> should be used for (a) {\em tasks that cannot run in parallel with
#> their own previous instances} because they would somehow interfere with each
#> other (use cycle time in all I/O paths to avoid this); and (b)
#> {\em Warm cycled forecast models that write out restart files for
#> multiple cycles ahead} (exception: see ``models with explicit restart
#> outputs'' below).\footnote{This is because you don't want Model(T)
#> waiting around to trigger off Model(T-12) if Model(T-6) has not
#> finished yet. If Model is forced to be sequential this can't happen
#> because Model(T) won't exist in the suite until Model(T-6) has
#> finished. But if Model(T-6) fails, it can be spawned-and-removed from
#> the suite so that Model(T) can {\em then} trigger off Model(T-12), 
#> which is the correct behaviour.} 
#>\begin{myitemize}
#>\item {\em section:}  [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\item {\em example:} \lstinline@sequential = ModelA, PostProcB@
#>\end{myitemize}

    one off = force_list( default=list())
#> One off tasks do not spawn a successor -they run once and are then removed
#> from the suite when they are no longer needed. {\em Startup} and {\em
#> cold start} tasks are automatically one off tasks and do not need
#> to be listed here.
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\item {\em example:} \lstinline@one off = TaskA, TaskB@
#>\end{myitemize}

    models with explicit restart outputs = force_list( default=list())
# TO DO: THESE TASKS COULD BE IDENTIFIED FROM THE GRAPH?

#> This is only required in the unlikely event that you want a warm
#> cycled forecast model to be able to start at the instant its restart
#> files are ready (if other prerequisites are satisfied) {\em before
#> its previous instance has finished}.  If so, the task has to depend
#> on a special output message emitted by the previous instance as soon as
#> its restart files are ready, instead of just on the previous instance
#> finishing. Tasks in this category must define special restart
#> output messages, {\em which must contain the word ``restart''}, in
#> [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[outputs]]] - see
#> Section~\ref{outputs}.
#>\begin{myitemize}
#>\item {\em section:} [special tasks]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\item {\em example:} \lstinline@models with explicit restart outputs = A, B@
#>\end{myitemize}

[task families]
#> \label{SuitercTaskFamilies}
#> A task family is a named group of tasks that appears as a single task
#> in the suite dependency graph. The entire family triggers as a group,
#> and downstream tasks can trigger off the entire family finishing. 
#> Task families can have internal dependencies, and family members
#> can also appear in the graph as non-family tasks. See
#> Section~\ref{TaskFamilies} for more information on task families.
    __many__ = force_list( default=None )
#> Replace MANY with each task family definition.
#>\begin{myitemize}
#>\item {\em section:} [task families]
#>\item {\em type:} list of task names (the family members)
#>\item {\em default:} None
#>\item {\em example (explicit):} \lstinline@ObsProc = ObsSurface, ObsSonde, ObsAircraft, ObsSat@
#>\item {\em example (expression):} \lstinline@ensemble = 'list( "m" + str(i) for i in range(1,6))'@
#>\end{myitemize}
#> The list of family members may be defined by an explicit list of task
#> names or a
#> list-generating Python expression (a ``list comprehension''). The
#> Python expression must be of the form \lstinline='list(...)'= and 
#> not \lstinline='[...]'=, and it must be quoted to hide the internal
#> comma in the range expression from the suite.rc parser. The
#> example above generates the task names \lstinline=m1, m2, ..., m5=. 
#> If tasks in a family share most configuration details, they can be 
#> defined all at once in a single subsection under \lstinline=[tasks]=.

[dependencies]
#> The suite dependency graph should be defined under this section.

    graph = string( default=None )
#> Define the graph of any one-off asynchronous tasks (no cycle time) here.
#> See Section~\ref{GraphDescrip} below for details.

    [[__many__]]
#> Replace MANY with each list of hours preceding a section of the suite
#> dependency graph, as required for differing dependencies at different
#> hours, {\em and} with any repeated asynchronous graph sections for 
#> satellite data processing or similar.
#>\begin{myitemize}
#>\item {\em section:} [dependencies]
#>\item {\em type:} list of integer hours, {\em or} string (for repeated asynchronous)
#>\item {\em legal values:} $0 \leq hour \leq 23$, {\em or} string
#>\item {\em default:} None
#>\item {\em example:} \lstinline@[[0,6,12,18]]@, {\em or} \lstinline@[[ASYNID:SAT-\d+]]@
#>\end{myitemize}

    graph = string
#> \label{GraphDescrip}
#> Define the dependency graph valid for specified list of hours or asynchronous ID pattern.
#> You can use the \lstinline=cylc graph= command, or right click 
#> Graph in gcylc, to plot the dependency graph as you
#> work on it.
#> See Section~\ref{DependencyGraphs} for details.
#>\begin{myitemize}
#>\item {\em section:} [dependencies] $\rightarrow$ [[HOURS]]
#>\item {\em type:} multiline string
#>\item {\em legal values:} {\em refer to section~\ref{DependencyGraphs}}
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

daemon = string( default=None )
#> For [[ASYNCID:pattern]] graph sections only, list any {\em
#> asynchronous daemon} tasks by name.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[ASYNCID:pattern]]
#>\item {\em type:} list of task names
#>\item {\em default:} empty list
#>\item {\em example:} \lstinline@daemon = A, B@
#>\end{myitemize}

[environment]
#> Use this section to define the global task execution environment, i.e.\
#> variables made available to all tasks. Order of definition 
#> is preserved. Even global variables can reference task name and cycle
#> time because suite and task identity are exported in the cylc job script 
#> prior to the user-defined environment. Cylc utility commands can be used in
#> variable assignment expressions because the cylc environment is exported
#> prior to user-defined variables. See {\em Task Execution Environment},
#> Section~\ref{TaskExecutionEnvironment}, for more information.
__many__ = string
#> Replace MANY with each global environment variable definition
#>\begin{myitemize}
#>\item {\em section:} [environment]
#>\item {\em type:} string
#>\item {\em default:} None
#>\item {\em legal values:} any environment variable assignment
#> expression valid in the {\em job submission shell}
#> (Appendix~\ref{JobSubShell}). White space around the `$=$' is allowed
#> (the \lstinline=suite.rc= file is not itself a shell script). 
#> \item {\em examples} for the bash shell: 
#>   \begin{myitemize}
#>       \item \lstinline@FOO = $HOME/bar/baz@
#>       \item \lstinline@BAR = ${FOO}$GLOBALVAR@
#>       \item \lstinline@BAZ = $(echo "hello world")@
#>       \item \lstinline@WAZ = ${FOO%.jpg}.png@
#>       \item \lstinline@NEXT_CYCLE = $( cylc cycletime -a 6 )@
#>       \item \lstinline@PREV_CYCLE = `cylc cycletime -s 6`@
#>       \item \lstinline@ZAZ = "${FOO#bar}"@
#>   \end{myitemize}
#> Variable expansion expressions containing the hash character must be
#> quoted because hash is the suite.rc comment delimiter.
#>\end{myitemize}

[directives]
#> Use this section to define batch queue scheduler directives, or similar, 
#> for all tasks in the suite.
#> These are written to the top of the job script that cylc submits when a
#> task is ready to run. Whether or not directives defined here are used
#> depends on the task's job submission method, which 
#> should also define the directive comment prefix
#> (`\lstinline=# @=' for loadleveler) and final directive ('\lstinline=# @ queue=').
__many__ = string
#> Replace MANY with each batch queue scheduler directive, e.g.\
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
#> \label{SuitercTasks}
    [[__many__]]
#> Replace MANY with each task name, followed by configuration items for that
#> task. Groups of tasks that need to be configured very similarly can be 
#> defined all at once under a single section here, by replacing the individual
#> task name with either a task family name, an explicit list of task names, 
#> or a list-generating Python expression (a ``list comprehension'').
#>\begin{myitemize}
#>\item {\em section:} [tasks]
#>\item {\em example (one task):} \lstinline@[[TaskX]]@
#>\item {\em example (family members):} \lstinline@[[FamilyF]]@
#>\item {\em example (explicit list):} \lstinline@[[A, B, C]]@
#>\item {\em example (expression):} \lstinline@[['list( "m" + str(i) for i in range(1,6))']]@
#>\end{myitemize}
#> Python list-generating expressions must be of the form
#> \lstinline='list(...)'= and not \lstinline='[...]'=, and they must be
#> quoted to hide the comma in the range expression from the suite.rc
#> parser. The example above generates the task names
#> \lstinline=m1, m2, ..., m5=.  
#> For grouped tasks, at least a few configuration items will
#> need to vary across the otherwise similar members. To allow this cylc
#> replaces the variable
#> \lstinline=$(TASK)= with the actual task name, at task definition time, 
#> in all configuration items.  Refer to the two ``generator''
#> example suites to see exactly how to use this feature.

    description = string( default="No description supplied" )
#> A description of the task, retrievable at run time
#> by the \lstinline=cylc show= command.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} ``No description supplied''
#>\item {\em example:}
#> \begin{lstlisting}
#> description = """
#> Here's what this task does ...
#> ... on a good day"""
#> \end{lstlisting}
#>\end{myitemize}

    command = force_list( default=list( "echo DUMMY $TASK_ID; sleep $CYLC_SIMULATION_SLEEP",))
#> This is the scripting to execute when the task is ready to run. If
#> omitted the task will run as a dummy task (see the default command
#> below). It can be a single command line or verbatim scripting inside
#> a multiline string. If a list of command lines (or of mulitline
#> scripting strings) is provided, the task
#> will automatically resubmit with the second command/script if the
#> first fails, and so on - this can be used for automated error
#> recovery.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} \lstinline="echo DUMMY $TASK_ID; sleep $CYLC_SIMULATION_SLEEP"=
#>\item {\em example:} \lstinline=GetData.sh OPTIONS ARGUMENTS=
#>\end{myitemize}

    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
#>Set the job submission method for this task, overriding the suite
#> default (if there is one). This
#>determines how cylc job scripts are executed when a task is
#>ready to run. See {\em Task Execution}, Section~\ref{TaskExecution}.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} 
#>   \begin{myitemize}
#>       \item \lstinline=background= - direct background execution
#>       \item \lstinline=at_now= - the rudimentary Unix `at' scheduler
#>       \item \lstinline=loadleveler= - loadleveler, generic (with
#> directives defined in the suite.rc file) 
#>       \item \lstinline=ll_ecox= - loadleveler, customized for
#>                    EcoConnect triplicate environment at NIWA
#>       \item \lstinline=ll_raw= - loadleveler, for existing job scripts
#>   \end{myitemize}
#>\item {\em default:} \lstinline=background=
#>\item {\em example:} \lstinline@job submission method = at_now@
#>\end{myitemize}

    job submission command template = string( default=None )
#> Set the command template for the job submission method.
#> The template should be suitable for substitution of the keys
#> {\em jobfile_path}, {\em stdout_file}, {\em stderr_file} in a dict.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a string template for a dict with keys
#> {\em jobfile_path}, {\em stdout_file}, {\em stderr_file}.
#>\item {\em default:} None (see suite level default)
#>\item {\em example:} \lstinline@llsubmit %(jobfile_path)s@
#>\end{myitemize}

    job submission log directory = string( default=None )
#> Set a job submission log directory for this task, overriding the suite
#> default, for the stdout and stderr logs from the job scripts
#> submitted by cylc when tasks are ready to run.
#> For monolithic tasks (which don't resubmit sub-jobs themselves) these will
#> be the complete job logs for the task.  For owned tasks, the suite
#> owner's home directory will be replaced by the task owner's.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} None (see suite level default)
#>\item {\em example:} \lstinline@ job submission log directory = $HOME/TaskXLogs/$CYLC_SUITE@
#>\end{myitemize}
#> {\em For remotely hosted tasks this configuration item is currently ignored - task
#> output logs are written to the remote task owner's home directory.} (This will be
#> addressed in a future cylc release).

    owner = string( default=None )
#> If a task has a defined owner, cylc will attempt to execute the task
#> as that user, according to the suite level {\em owned task execution method}
#> for local tasks, or by passwordless ssh for remote tasks.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid username on the task host
#>\item {\em default:} None
#>\item {\em example:} \lstinline@owner = alice@
#>\end{myitemize}

    remote host = string( default=None )
#> If a task specifies a remote host, cylc will attempt to execute the
#> task on that host, using the specified job submission method, by
#> passwordless ssh. The relevant suite
#> task scripts and executables, and cylc itself, must be installed on the 
#> remote host. The task must also specify {\em remote cylc directory}
#> and {\em remote suite directory}. 
#> An {\em owner} must be defined if the task owner's username on the
#> remote host is not the same as the local suite owner's. Passwordless
#> ssh must be configured between the local suite owner and remote
#> task owner accounts.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid hostname on your network
#>\item {\em default:} None
#>\item {\em example:} \lstinline@remote host = thor.niwa.co.nz@
#>\end{myitemize}

    remote shell template = string( default=None )
#> A template of the remote shell command for a submitting a remote task.
#> The template should be suitable for substitution of the keys
#> {\em destination}, {\em jobfile_path} and {\em command} in a dict.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a string template for a dict with keys
#> {\em destination}, {\em jobfile_path} and {\em command}.
#>\item {\em default:} None
#>\end{myitemize}

    remote cylc directory = string( default=None )
#> For remotely hosted tasks, this must be used to specify
#> the path to the cylc installation (i.e.\ \lstinline=$CYLC_DIR=)
#> on the remote host.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid directory path on the remote host
#>\item {\em default:} None
#>\item {\em example:} \lstinline@remote cylc directory = /path/to/cylc/on/remote/host@
#>\end{myitemize}
#> Every remotely hosted task must set this item, either here or at
#> suite level.

    remote suite directory = string( default=None )
#> For remotely hosted tasks, this specifies 
#> the path to the suite definition directory 
#> on the remote host, in order to give the task access to
#> files in the stored there (via \lstinline=$CYLC_SUITE_DIR=) and in the 
#> suite bin directory (via \lstinline=$PATH=).
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid directory path on the remote host
#>\item {\em default:} None
#>\item {\em example:} \lstinline@remote suite directory = /path/to/suite/on/remote/host@
#>\end{myitemize}
#> This item is not compulsory for remotely hosted tasks, because 
#> some tasks may not require access to files in the suite definition
#> directory.
 
#>IGNORE
    task submitted hook script = string( default=None )
    task submission failed hook script = string( default=None )
    task started hook script = string( default=None )
    task succeeded hook script = string( default=None )
    task failed hook script = string( default=None )
    task warning hook script = string( default=None )
    task timeout hook script = string( default=None )
#>RESUME

#> \paragraph{    task EVENT hook scripts}
#>
#> Task event hooks facilitate centralized alerting for critical events.
#> The following hooks are available:
#>\begin{myitemize}
#>\item {\bf task submitted hook script}
#>\item {\bf task submission failed hook script}
#>\item {\bf task started hook script}
#>\item {\bf task succeeded hook script}
#>\item {\bf task failed hook script}
#>\item {\bf task warning hook script}
#>\item {\bf task timeout hook script}
#>\end{myitemize}
#> These are task-specific hooks; you can also set suite level defaults.
#> Cylc provides a hook script that sends emails: cylc email-alert.
#> Your own hook scripts can be located in suite bin directories. 
#> Hook scripts are passed the following arguments:
#> \begin{lstlisting}
#> <hook-script> EVENT SUITE TASKID MESSAGE
#> \end{lstlisting}
#> where MESSAGE describes what has happened; EVENT is 
#> either `submitted', `started', `succeeded', `failed', `timeout', 
#> or `submission\_failed'; and TASKID is the unique task identifier
#> (e.g.\ \lstinline=NAME%CYCLE_TIME= for cycling tasks).
#> Note that {\em hook scripts are called by cylc, not by tasks,} 
#> so if you wish to pass in additional information via the environment, 
#> use the [cylc local environment] section, not [environment].
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} string
#>\item {\em default:} None
#>\item {\em example:} \lstinline@task failed hook script = cylc email-alert@
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
#> (or started), the task timeout hook script will be called by cylc with the
#> following arguments:
#> \begin{lstlisting}
#> <script> EVENT SUITE TASKID MESSAGE
#> \end{lstlisting}
#> where MESSAGE describes what has happened; EVENT is `submission' or
#> `execution'; and TASKID is the unique task identifier
#> (e.g.\ \lstinline=NAME%CYCLE_TIME= for cycling tasks).
#> Like the hook scripts, these are task-specific settings; you can also
#> set suite level defaults.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} float (minutes)
#>\item {\em default:} None
#>\item {\em example:} \lstinline@task execution timeout in minutes = 10@
#>\end{myitemize}

    reset execution timeout on incoming messages = boolean( default=True )
#> If True, and you have set an execution timeout, the timer will 
#> reset to zero every time a message is received from a running task.
#> Otherwise, the task will timeout if it does not finish in time,
#> even if it last sent a message (and was, by implication, still alive) 
#> within the timeout interval.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em example:} \lstinline@reset execution timeout on incoming messages = False@
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
#>\item {\em example:} \lstinline@extra log files = /a/b/c, /d/e/f@
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
#>\item {\em example:} \lstinline@hours = 6,18
#>\end{myitemize}
#>RESUME

    manual task completion messaging = boolean( default=None )
#> If a task's initiating process detaches and exits before task
#> processing is finished, then cylc cannot arrange for the task to
#> automatically signal when it has succeeded or failed. In such cases
#> you must insert some minimal cylc messaging in appropriate places in
#> the task implementation. There is an equivalent global setting in the
#> unlikely event that all, or most, of your tasks are in this category.
#>\begin{myitemize}
#>\item {\em section:} (top level)
#>\item {\em type:} boolean
#>\item {\em default:} \lstinline=None= 
#>\item {\em example:} \lstinline@manual task completion messaging = True@
#>\end{myitemize}

        [[[environment]]]
#> Use this section to define the task-specific task execution
#> environment. Variables defined here may refer to variables in
#> the global environment. Order of definition is preserved. 
#> Cylc utility commands can be used in variable
#> assignment expressions because the cylc environment is defined
#> prior to the user-defined environment.
#> See {\em Task Execution Environment}
#> (Section~\ref{TaskExecutionEnvironment}) for more information.
        __many__ = string
#> Replace MANY with each task environment variable definition.
#>\begin{myitemize}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[environment]]]
#>\item {\em type:} string
#>\item {\em legal values:} any environment variable assignment
#> expression valid in the {\em job submission shell}. 
#> White space around the `$=$' is allowed (the
#> \lstinline=suite.rc= file is not a shell script). 
#> \item {\em examples:} for the bash shell: 
#>   \begin{myitemize}
#>       \item \lstinline@FOO = $HOME/bar/baz@
#>       \item \lstinline@BAR = ${FOO}$GLOBALVAR@
#>       \item \lstinline@BAZ = $(echo "hello world")@
#>       \item \lstinline@WAZ = ${FOO%.jpg}.png@
#>       \item \lstinline@NEXT_CYCLE = $( cylc cycletime --add=6 )@
#>       \item \lstinline@PREV_CYCLE = `cylc cycletime -s 6`@
#>       \item \lstinline@ZAZ = "${FOO#bar}"@
#> Variable expansion expressions containing the hash character must be
#> quoted because hash is the suite.rc comment delimiter.
#>   \end{myitemize}
#>\item {\em default:} None
#>\end{myitemize}

        [[[directives]]]
#> Use this section to define task-specific batch queue
#> scheduler directives, or similar, for this task.
#> These are written to the top of the job script that cylc submits when the
#> task is ready to run. Whether or not directives defined here are used
#> depends on the task's job submission method, which should also 
#> define the directive comment prefix
#> (`\lstinline=# @=' for loadleveler) and final directive (`\lstinline=# @ queue=').
        __many__ = string
#> Replace MANY with each task batch queue scheduler directive.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[directives]]]
#>\item {\em type:} string
#>\item {\em legal values:} any legal directive for your batch scheduler
#>\item {\em default:} None
#>\item {\em example:} \lstinline@class = parallel@
#>\end{myitemize}

        [[[outputs]]]
#> \label{outputs}
#> {\em Only required if other tasks trigger off specific {\em internal
#> outputs} of this task}, as opposed to triggering off it finishing.
#> The task implementation must report the specified output message 
#> by calling \lstinline=cylc task message OUTPUT_MESSAGE= when the
#> corresponding real output has been completed.
        __many__ = string
#> Replace MANY with each output message definition, for any explicit output
#> messages emitted by this task and depended on by other tasks in the 
#> dependency graph.
#>\begin{myitemize}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]] $\rightarrow$ [[[outputs]]]
#>\item {\em type:} string
#>\item {\em legal values:} a message containing
#>           \lstinline=$(CYCLE_TIME)= with an optional offset as shown
#> below. {\bf Note the round parentheses} - this is not a shell
#> variable, although without an offset it does correspond to 
#> the \lstinline=$CYCLE_TIME= in the task execution environment.
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

[simulation mode]
#> Configuration items specific to running suites in simulation mode.
clock offset from initial cycle time in hours = integer( default=24 )
#> Specify a clock offset of 0 to simulate real time operation, greater 
#> than zero to simulate catching up from a delay and transitioning to
#> real time operation.
#>\begin{myitemize}
#>\item {\em section:} [simulation mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $\geq 0$
#>\item {\em default:} 24
#>\item {\em example:} \lstinline@clock offset from initial cycle time in hours = 6@
#>\end{myitemize}

clock rate in seconds per simulation hour = integer( default=10 )
#> This determines the speed at which the simulation mode clock runs. A value
#> of 10, for example, means it will take 10 simulation seconds to simulate
#> one hour of real time operation.
#>\begin{myitemize}
#>\item {\em section:} [simulation mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $\geq 0$
#>\item {\em default:} 10
#>\item {\em example:} \lstinline@clock rate in seconds per simulation hour = 20 @
#>\end{myitemize}

# exported as $CYLC_SIMULATION_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
#> Set the approximate number of {\bf real} seconds that a dummy task
#> takes to execute.
#>\begin{myitemize}
#>\item {\em section:} [simulation mode]
#>\item {\em type:} integer
#>\item {\em legal values:} $\geq 0$
#>\item {\em default:} 10
#>\item {\em example:} \lstinline@task run time in seconds = 20@
#>\end{myitemize}

#>IGNORE
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
#> For testing purposes you can also choose to have dummy tasks executed
#> job submission methods (you are unlikely to need this).
#>\begin{myitemize}
#>\item {\em section:}  [simulation mode]
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
#>\item {\em example:} \lstinline@job submission method = at_now@
#>\end{myitemize}
#>RESUME

[visualization]
#> Graph plotting configuration items for suite.rc and run time graphs. 
#> These do not affect the graph-based suite control interface.

initial cycle time = integer( default=2999010100 )
#> Initial cycle time for graph plotting.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} integer
#>\item {\em default:} 2999010100
#>\item {\em example:} \lstinline@initial cycle time = 2011052318@
#>\end{myitemize}

final cycle time = integer( default=2999010123 )
#> Final cycle time for graph plotting. This should typically be just
#> far enough ahead of the initial cycle time to show the full suite.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} integer
#>\item {\em default:} 2999010123
#>\item {\em example:} \lstinline@final cycle time = 2011052318@
#>\end{myitemize}

show family members = boolean( default=False )
# TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS?
#> Whether to plot task family members, or the family as a whole. 
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@show family members = True@
#>\end{myitemize}

use node color for edges = boolean( default=True )
#> Outgoing graph edges (dependency arrows) can be plotted in the same
#> color as the upstream node (task); this can make it easier to follow a
#> path through a complex graph. 
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} boolean
#>\item {\em default:} True
#>\item {\em example:} \lstinline@use node color for edges = False@
#>\end{myitemize}

default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=box'))
#> Set the default attributes (color and style etc.) of graph nodes (tasks).
#> Attribute pairs must be quoted to hide the \lstinline@=@ character in them.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} list of {\em quoted} \lstinline@'attribute=value'@ pairs
#>\item {\em legal values:} see graphviz or pygraphviz documentation
#>\item {\em default:} \lstinline@'style=unfilled', 'color=black', 'shape=ellipse'@
#>\item {\em example:} \lstinline@default node attributes = 'style=filled', 'shape=box'@
#>\end{myitemize}

default edge attributes = force_list( default=list('color=black'))
#> Set the default attributes (color and style etc.) of graph edges
#> (dependency arrows).
#> Attribute pairs must be quoted to hide the \lstinline@=@ character in them.
#>\begin{myitemize}
#>\item {\em section:}  [visualization]
#>\item {\em type:} list of graph edge attributes
#>\item {\em legal values:} see graphviz or pygraphviz documentation
#>\item {\em default:} \lstinline@'color=black'@
#>\item {\em example:} \lstinline@default edge attributes = 'color=red'@
#>\end{myitemize}

[[node groups]]
#> Define named groups of graph nodes (tasks) that can have
#> attributes assigned to them en masse in the [[node attributes]] section.
    __many__ = force_list( default=list())
#> Replace MANY with each node group.
#> Tasks can appear in multiple groups.
#>\begin{myitemize}
#>\item {\em section:}  [visualization] $\rightarrow$ [[node groups]]
#>\item {\em type:} list of task names
#>\item {\em default:} empty
#>\item {\em example:} \lstinline@BigModels = TaskX, TaskY@
#>\end{myitemize}

[[node attributes]]
#> Here you can assign graph node attributes to specific tasks or named
#> groups of tasks defined in the [[node groups]] section.
    __many__ = force_list( default=list())
#> Replace MANY for any specific tasks or named groups that you want to 
#> assign attributes to.
#>\begin{myitemize}
#>\item {\em section:} [visualization] $\rightarrow$ [[node attributes]]
#>\item {\em type:} list of {\em quoted} \lstinline@'attribute=value'@ pairs
#>\item {\em legal values:} see graphviz or pygraphviz documentation
#>\item {\em default:} None
#>\item {\em example:}
#>\begin{lstlisting}
#>   BigModels = 'style=filled', 'color=blue'
#>   TaskX = 'color=red'
#>\end{lstlisting}
#>\end{myitemize}

[[run time graph]]
#> Cylc can generate run time graphs of resolved dependencies, i.e. what 
#> actually triggers off what as the suite runs.
#> Use simulation mode to generate run time graphs very quickly.

enable = boolean( default=False )
#> Run time graphing is disabled by default because it is mainly intended
#> for cylc development and debugging (the run time graph can be compared
#> with the suite.rc graph to ensure that new suite.rc graph elements are
#> parsed correctly).
#>\begin{myitemize}
#>\item {\em section:} [visualization][[run time graph]]
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@enable = True@
#>\end{myitemize}

cutoff in hours = integer( default=24 )
#> Each new task will be added to the run time graph, as the suite 
#> runs, unless its cycle time exceeds the initial cycle time by more
#> than this cutoff value.
#>\begin{myitemize}
#>\item {\em section:} [visualization][[run time graph]]
#>\item {\em type:} integer
#>\item {\em legal values:} $>=0$
#>\item {\em default:} 24
#>\item {\em example:} \lstinline@cutoff in hours = 12@
#>\end{myitemize}

directory = string( default='$CYLC_SUITE_DIR/graphing')
#> Where to put the run time graph file, called \lstinline=runtime-graph.dot=.
#>\begin{myitemize}
#>\item {\em section:}  [visualization][[run time graph]]
#>\item {\em type:} string
#>\item {\em legal values:} a valid local file path
#>\item {\em default:} \lstinline=$CYLC_SUITE_DIR/graphing=
#>\item {\em example:} \lstinline@directory = $HOME/mygraph@
#>\end{myitemize}

[task insertion groups]
#> Define named groups of tasks that can be inserted into a suite en mass, as 
#> if inserting a single task.
#> May be useful for groups of related cold start tasks, for instance.
 __many__ = force_list()
#> Replace MANY with each task insertion group.
#>\begin{myitemize}
#>\item {\em section:} [task insertion groups]
#>\item {\em type:} list of task names
#>\item {\em default:} None
#>\item {\em example:} \lstinline@NWPCold = ColdX, ColdY@
#>\end{myitemize}

[cylc local environment]
#> Use this section to add variables to the environment in which cylc
#> itself runs. These variables will be available to processes
#> spawned directly by cylc, namely timeout and alert hook
#> scripts. {\em Do not use this section to alter the task execution
#> environment - use the plain [environment] sections for that - 
#> variables defined in this section will only be available 
#> to tasks if local direct job submission methods are used}. 
__many__ = string
#> Replace MANY with each cylc local environment variable definition.
#>\begin{myitemize}
#>\item {\em section:} [cylc local environment]
#>\item {\em type:} string
#>\item {\em default:} None
#>\item {\em legal values:} any valid environment variable assignment
#> expression. White space around the `$=$' is fine (the
#> \lstinline=suite.rc= file is not a shell script). 
#> \item {\em examples:} for the bash shell: 
#>   \begin{myitemize}
#>       \item \lstinline@FOO = $HOME/bar/baz@
#>       \item \lstinline@BAZ = $(echo "hello world")@
#>       \item \lstinline@WAZ = ${FOO%.jpg}.png@
#>   \end{myitemize}
#>\end{myitemize}

[experimental]
#> Section for experimenting with new configuration items
live graph movie = boolean( default=False )
#> Turning this item on will result in a new dot file being written to the 
#> suite graphing directory every time the suite state changes. These
#> can later be converted into movie frames and animated with appropriate 
#> image processing tools. A script for automating this is 
#> currently in the cylc development repository.
#>\begin{myitemize}
#>\item {\em section:} [experimental]
#>\item {\em type:} boolean
#>\item {\em default:} False
#>\item {\em example:} \lstinline@live graph movie = True@
#>\end{myitemize}


#>IGNORE
# This section is for development purposes only and is ignored by
# document processing. It can be used to test new task proxy class
# developments without bothering with suite.rc graph parsing. New items
# may be added here for use in config.py:load_raw_task_definitions().
[raw task definitions]
    [[__many__]]
    description = string( default="No description supplied" )
    command = force_list( default=list( "echo DUMMY $TASK_ID; sleep $CYLC_SIMULATION_SLEEP",))
    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
    job submission log directory = string( default=None )
    owner = string( default=None )
    remote host = string( default=None )
    remote cylc directory = string( default=None )
    remote suite directory = string( default=None )
    task submitted hook script = string( default=None )
    task submission failed hook script = string( default=None )
    task started hook script = string( default=None )
    task succeeded hook script = string( default=None )
    task failed hook script = string( default=None )
    task warning hook script = string( default=None )
    task timeout hook script = string( default=None )
    task submission timeout in minutes = float( default=None )
    task execution timeout in minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )
    extra log files = force_list( default=list())
    #hours = force_list() # e.g. 0,6,12,18
    hours string = string(default=None)  # e.g. "0,6,12,18"
    manual task completion messaging = boolean( default=None )

    type = option( free, async_daemon, async_repeating, async_oneoff )
    asyncid pattern = string( default=None )

    # oneoff, sequential, tied, clocktriggered
    type modifiers = force_list( default=list() )

    clock trigger offset in hours = float( default=0.0 )

        [[[prerequisites]]]
        __many__ = string

        [[[startup prerequisites]]]
        __many__ = string

        [[[environment]]]
        __many__ = string
        [[[directives]]]
        __many__ = string
        [[[outputs]]]
        __many__ = string
#> RESUME
