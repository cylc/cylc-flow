#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import re
from job_submit import job_submit
from cylc.TaskID import TaskID

class loadleveler( job_submit ):

    "Loadleveler job submission"

    COMMAND_TEMPLATE = "llsubmit %s"
    REC_ID = re.compile(r"""\Allsubmit:\sThe\sjob\s"(?P<id>[^"]+)"\s""")
    REC_PROCESSED_FILTER = re.compile(
        r"^llsubmit: Processed command file through Submit Filter:")

    def set_directives( self ):
        self.jobconfig['directive prefix'] = "# @"
        self.jobconfig['directive connector'] = " = "
        self.jobconfig['directive final'] = "# @ queue"

        defaults = {}
        defaults[ 'job_name' ] = self.suite + TaskID.DELIM + self.task_id
        # Replace literal '$HOME' in stdout and stderr file paths with '' 
        # because environment variables are not interpreted in directives.
        # (For remote tasks the local home directory path is replaced
        # with '$HOME' in config.py).
        defaults[ 'output'   ] = re.sub( '\$HOME/', '', self.stdout_file )
        defaults[ 'error'    ] = re.sub( '\$HOME/', '', self.stderr_file )

        # NOTE ON SHELL DIRECTIVE: on AIX at NIWA '#@ shell = /bin/bash'
        # results in the job executing in a non-login shell (.profile
        # not sourced) whereas /bin/ksh does get a login shell. WTF?! In
        # any case this directive appears to affect only the shell *from
        # which the task job script is executed*, NOT the shell *in which it
        # is executed* (that is determined by the '#!' at the top of the
        # task job script).
        defaults[ 'shell'    ] = '/bin/ksh'

        # NOTE if the initial "running dir" does not exist (or is not
        # writable by the user?) loadleveler will hold the job. Use
        # the 'initialdir' directive to fix this.

        # In case the user wants to override the above defaults:
        for d,val in self.jobconfig['directives'].items():
            defaults[ d ] = val
        self.jobconfig['directives'] = defaults

    def construct_jobfile_submission_command( self ):
        """
        Construct a command to submit this job to run.
        """
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.__class__.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path )

    def filter_output( self, out, err):
        """Filter the stdout/stderr output - suppress process message."""
        new_err = ""
        for line in err.splitlines():
            if not self.REC_PROCESSED_FILTER.match(line):
                new_err += line + "\n"
        return out, new_err

    def get_id( self, out, err ):
        """
        Extract the job submit ID from job submission command
        output. For background jobs the submission command simply
        echoes the process ID to stdout as described above.
        """
        for line in str(out).splitlines():
            match = self.REC_ID.match(line)
            if match:
                return match.group("id")

    def get_job_poll_command( self, jid ):
        """
        Given the job submit ID, return a command string that uses
        'cylc get-task-status' to determine current job status:
           cylc get-job-status <QUEUED> <RUNNING>
        where:
            QUEUED  = true if job is waiting or running, else false
            RUNNING = true if job is running, else false

        WARNING: 'cylc get-task-status' prints a task status message -
        the final result - to stdout, so any stdout from scripting prior
        to the call must be dumped to /dev/null.

        Loadleveler has MANY possible job states; I think we only need:
          * 'I' (idle?) = waiting in the loadleveler queue
          * 'R' (running) or 'ST' (starting) = running
        """
        cmd = ( "RUNNING=false; QUEUED=false; "
                + "llq -f %id %st " + jid + " | grep " + jid
                + " | awk \"{ print \$2 }\" | egrep \"^(R|ST)$\" > /dev/null; "
                + "[[ $? == 0 ]] && RUNNING=true && QUEUED=true; "
                + "if ! $QUEUED; then "
                + "  llq -f %id %st " + jid
                + "   | awk \"{ print \$2 }\" | egrep \"^I$\" > /dev/null; "
                + "  [[ $? == 0 ]] && QUEUED=true; "
                + "fi; "
            + " cylc get-task-status " + self.jobfile_path + ".status $QUEUED $RUNNING" )
        return cmd

    def get_job_kill_command( self, jid ):
        """
        Given the job submit ID, return a command to kill the job.
        Note that llcancel does not report successful job kill, just:
        "Cancel command has been sent to the central manager"
        """
        cmd = "llcancel " + jid
        return cmd

