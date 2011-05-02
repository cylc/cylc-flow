#>\subsection{Global Settings}

title = string( default="No suite title given" )
#>The suite title is displayed in the gcylc
#> suite database gui, and can also be retrieved by the 
#> \lstinline=cylc show= command.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:} Top level.
#>\item {\em default:} ``No suite title given''
#>\end{itemize}

description = string( default="No suite description given" )
#>The suite description can be retrieved via the 
#>gcylc gui or the \lstinline=cylc show= command.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:} Top level.
#>\item {\em default:} ``No suite description given''
#>\end{itemize}

job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=background )
#>The default job submission method for the suite,
#>which determines how cylc job scripts are executed when a task is
#>ready to run. See Section~\ref{JobSubmissionMethods}.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em legal values:} 
#>   \begin{itemize}
#>       \item \lstinline=background= - direct subshell execution in the background 
#>       \item \lstinline=at_now= - the rudimentary Unix 'at' scheduler
#>       \item \lstinline=loadleveler= - loadleveler generic
#>       \item \lstinline=ll_ecox= - loadleveler, NIWA EcoConnect environment
#>       \item \lstinline=ll_raw= - loadleveler for prepared script
#>   \end{itemize}
#>\item {\em default:} \lstinline=background=
#>\item {\em individual task override:} yes
#>\end{itemize}

owned task execution method = option( sudo, ssh, default=sudo )
#>The method by which tasks owned by users
#>other than the suite owner are submitted to run.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em legal values:}
#>   \begin{itemize}
#>        \item sudo (\lstinline=sudo -u owner [job submission method] TASK=)
#>        \item ssh (\lstinline=ssh owner@host [job submission method] TASK=)
#>   \end{itemize}
#>\item {\em default:} \lstinline=sudo=
#>\end{itemize}

job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
#>The shell used to interpret
#>job scripts (i.e.\ the scripts submitted by cylc when a task is ready 
#>to run).  This potentially affects the way that \lstinline=suite.rc= 
#> environment sections are converted to scripting (currently hardwired
#> in cylc - would need to change this to use csh for example), and how
#> the user writes \lstinline=suite.rc= {\em scripting} sections.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em legal values:}
#>   \begin{itemize}
#>        \item \lstinline=/bin/bash=
#>        \item \lstinline=/bin/ksh=
#>        \item \lstinline=/usr/bin/bash=
#>        \item \lstinline=/usr/bin/ksh=
#>   \end{itemize}
#>\item {\em default:} \lstinline=/bin/bash= 
#>\end{itemize}

use lockserver = boolean( default=True )
#>Use of the cylc lockserver prevents
#> accidental or deliberate invocation of multiple instances of the same
#> suite, and accidental invocation of a suite task using
#> \lstinline=cylc submit= when the same task is already running in its
#> suite.  It will allow invocation of the same suite under a different
#> registration GROUP:NAME if and only if the suite declares itself to
#> be capable of that (which implies all I/O is dynamically configured
#> to be suite registration specific)
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:}  Top level.
#>\item {\em default:} True
#>\end{itemize}

use secure passphrase = boolean( default=False )
#>If True, any intervention in a
#> running suite will require use of a secure passphrase. The mechanism
#> has little overhead to the user, however - a passphrase stored with
#> secure permissions under \lstinline=$HOME/.cylc/security/GROUP:NAME=
#> is automatically used if it exists. It must be present in
#> any user account that needs access to the suite (if tasks run on a 
#> remote host for instance). The passphrase itself is never transferred
#> across the network (a secure MD5 checksum is).  As for ssh, this
#> guarantees security so long as your user account isn't breached.
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:}  Top level.
#>\item {\em default:} False
#>\end{itemize}

dummy mode only = boolean( default=False )
#>If True, cylc will abort if you try to run
#>the suite in real mode. Can be used for demo suites that have been
#>copied out of their working environment and thus can't be run for real.
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:}  Top level.
#>\item {\em default:} False
#>\end{itemize}

allow multiple simultaneous instances = boolean( default=False )
#>Declares that all suite is I/O unique per
#> suite registration - i.e.\ all I/O paths include the suite registration 
#> group and name so
#> that multiple instances of the same suite can be run at once 
#> (under different registrations) without interference. If not, 
#> the lockserver will not allow another instance of the suite to start.
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:}  Top level.
#>\item {\em default:} False
#>\end{itemize}

maximum runahead hours = integer( min=0, default=24 )
#>This is the maximum difference in cycle time
#>that cylc allows between the fastest and slowest task in the suite.
#>Clock-triggered tasks with no other prerequisites, for example, will
#>rapidly spawn out to the runahead limit in catch up operation.
#>\begin{itemize}
#>\item {\em type:} integer, minimum 0
#>\item {\em section:}  Top level.
#>\item {\em default:} 24
#>\end{itemize}

number of state dump backups = integer( min=1, default=10 )
#> Length of the rolling archive of state dump files automatically
#> maintained by cylc. Every time anything changes cylc updates the
#> state dump file that allows a suite to be restarted from a previous
#> state. Keeping backups guards against, for example, hardware failing
#> while the file is being updated (unlikely but possible).
#>\begin{itemize}
#>\item {\em type:} integer, minimum 1
#>\item {\em section:}  Top level.
#>\item {\em default:} 10
#>\end{itemize}

roll log at startup = boolean( default=True )
#>Roll (i.e. back up and start anew), or not,
#>the cylc suite log file, every time the suite is started or restarted.
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:} Top level.
#>\item {\em default:} True
#>\end{itemize}

use suite blocking = boolean( default=False )
#>'Blocking' a suite causes it to refuse to
#> comply with subsequent intervention commands until deliberately
#> 'unblocked'. This is a crude security measure to guard against
#> accidental intervention in your own suites. It may be useful when
#> running multiple suites at once, or when running particularly
#> important suites, but is disabled by default because it is
#> fundamentally annoying. (Consider also that any intervention
#> results in a special state dump from which you can restart the suite 
#> if you decide the intervention was a mistake).
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:} Top level. 
#>\item {\em default:} False
#>\end{itemize}

ignore task owners = boolean( default=False )
#>This turns off special treatment of owned tasks
#> (namely invocation of the job submission method via sudo or ssh as owner).
#> Can be useful when testing such a suite outside of its normal operational
#> environment.
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:} Top level.
#>\item {\em default:} False
#>\end{itemize}

use quick task elimination = boolean( default=True )
#>When removing finished tasks from the suite as
#> early as possible, take account of tasks known to have no downstream
#> dependents in later (as opposed to its own) forecast cycles.
#>\begin{itemize}
#>\item {\em type:} boolean
#>\item {\em section:} Top level.
#>\item {\em default:} True
#>\end{itemize}

top level state dump directory = string( default = '$HOME/.cylc/state' )
#>The top-level directory under which cylc
#> stores suite-specific state dump files (which can be used to restart
#> a suite from an earlier state).
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:} Top level.
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/.cylc/state=
#>\end{itemize}

top level logging directory = string( default = '$HOME/.cylc/logging' )
#>The top-level directory under which cylc 
#> stores suite-specific scheduler log files.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:} Top level.
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/.cylc/logging=.
#>\end{itemize}

job submission log directory = string( default='$HOME/CylcLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME' )
#>The directory in which to put the stdout and stderr
#> log files for the job scripts submitted by cylc when a task is ready to run.
#> For monolithic tasks (which don't resubmit sub-jobs themselves) these will
#> be the complete job logs for the task.  For owned tasks, the suite
#> owner's home directory will be replaced by the task owner's.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:} Top level.  
#>\item {\em legal values:} absolute path, may contain environment
#> variables such as \lstinline=$HOME=.
#>\item {\em default:} \lstinline=$HOME/CylcLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME=
#>\end{itemize}

task submitted hook = string( default=None )
#>Script to call whenever a task is submitted.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:} Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task started hook = string( default=None )
#> Script to call whenever a task reports that it has started running.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task finished hook = string( default=None )
#>Script to call whenever a task reports that it has finished successfully.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task failed hook = string( default=None )
#>Script to call whenever a task reports that it has failed.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task warning hook = string( default=None )
#>script to call whenever a task reports a warning message.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task submission failed hook = string( default=None )
#>Script to call whenever job submission fails
#> for a task (in which case it will not start running).
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task timeout hook = string( default=None )
#>Script to call whenever a task times out (in job submission or execution).
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task submission timeout minutes = float( default=None )
#>If a task fails to report that it has started 
#> this long after it was submitted, call the task timeout hook script.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

task execution timeout minutes = float( default=None )
#> If a task fails to report that it has completed
#> (or failed) this long after it reported that it had started running,
#> call the task timeout hook script.
#>\begin{itemize}
#>\item {\em type:} string
#>\item {\em section:}  Top level.
#>\item {\em default:} None
#>\item {\em individual task override:} yes
#>\end{itemize}

tasks to include at startup = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  Top level.
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

tasks to exclude at startup = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  Top level.
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


# global scripting section
pre-command scripting = string( default='' )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  Top level.
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

post-command scripting = string( default='' )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  Top level.
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

 
[dummy mode]
# dummy mode was most useful prior to cylc-3: it allowed us to get the
# scheduling right without running real tasks when a suite was defined
# entirely by a collection of distinct "task definition files" whose
# prerequisites and outputs had to be consistent across the suite.
# Now (post cylc-3) it is primarily useful for cylc development, and
# for generating run-time dependency graphs very quickly.
clock offset from initial cycle time in hours = integer( default=24 )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [dummy mode]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

clock rate in seconds per dummy hour = integer( default=10 )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [dummy mode]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [dummy mode]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [dummy mode]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[special tasks]
    startup = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [special tasks]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    coldstart = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    oneoff = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    sequential = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    # outputs MUST contain the word 'restart':
    models with explicit restart outputs = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    # offset can be a float:
    clock-triggered = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [special tasks]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[task families]
    __many__ = force_list( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [task families]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[dependencies]
    # dependency graphs under cycle time lists:
    [[__many__]]
    graph = string
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [dependencies][[(hours)]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[experimental]
# generate a distinct graph for each timestep
live graph movie = boolean( default=False )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [experimental]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[visualization]
# hours after which to stop plotting the run time graph
when to stop updating = integer( default=24 )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

# absolute, or relative to $CYLC_SUITE_DIR for portability
run time graph directory = string( default='$CYLC_SUITE_DIR/graphing')
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

run time graph filename  = string( default='runtime.dot')
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

# TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS
show family members = boolean( default=False )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

use node color for edges = boolean( default=True )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=ellipse'))
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

default edge attributes = force_list( default=list('color=black'))
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[[node groups]]
    __many__ = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [visualization][[node groups]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

[[node attributes]]
    # item is task name or task group name
    __many__ = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [visualization][[node attributes]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[task insertion groups]
 __many__ = force_list()
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [task insertion groups]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


[environment]
__many__ = string
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [environment]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


# Global directives.
# Prefix ('# @') and final directive ('# @ queue') supplied by job submission method.
[directives]
__many__ = string
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [directives]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


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
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    job submission log directory = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task submitted hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task started hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task finished hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task failed hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task warning hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task submission failed hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task timeout hook = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    task submission timeout minutes = float( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    execution timeout minutes = float( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    reset execution timeout on incoming messages = boolean( default=True )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    pre-command scripting = string( default='' )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    post-command scripting = string( default='' )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    # default to dummy task:
    command = force_list( default=list( cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    owner = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    host = string( default=None )
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    # hours required to use ('submit' or 'insert') tasks not in the
    # graph; if present graphed hours must not conflict with this.
    hours = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

    extra log files = force_list( default=list())
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

        [[[environment]]]
        __many__ = string
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:}  [tasks] $\rightarrow$ [[TASK]][[[environment]]]
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

        [[[directives]]]
        # Prefix ('# @') and final directive ('# @ queue') supplied 
        # by job submission method.
        __many__ = string
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} 
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}

          [[[outputs]]]
        __many__ = string
#>\begin{itemize}
#>\item {\em type:}
#>\item {\em section:} 
#>\item {\em legal values:}
#>   \begin{itemize}
#>       \item 
#>   \end{itemize}
#>\item {\em default:}
#>\end{itemize}


