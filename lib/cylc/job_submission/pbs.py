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

class pbs( job_submit ):

    "PBS qsub job submission."

    COMMAND_TEMPLATE = "qsub %s"

    def set_directives( self ):
        self.jobconfig['directive prefix'] = "#PBS"
        self.jobconfig['directive final']  = None
        self.jobconfig['directive connector'] = " "

        defaults = {}
        defaults[ '-N' ] = self.task_id
        # Replace literal '$HOME' in stdout and stderr file paths with '' 
        # because environment variables are not interpreted in directives.
        # (For remote tasks the local home directory path is replaced
        # with '$HOME' in config.py).
        defaults[ '-o' ] = re.sub( '\$HOME/', '', self.stdout_file )
        defaults[ '-e' ] = re.sub( '\$HOME/', '', self.stderr_file )

        # In case the user wants to override the above defaults:
        for d,val in self.jobconfig['directives'].items():
            defaults[ d ] = val
        # PBS requires jobs names <= 15 characters
        # This restriction has been removed at PBS version 11
        # but truncating to 15 chars should not cause any harm.
        if len( defaults[ '-N' ] ) > 15:
            defaults[ '-N' ] = defaults[ '-N' ][:15]
        self.jobconfig['directives'] = defaults

    def construct_jobfile_submission_command( self ):
        """
        Construct a command to submit this job to run.
        """
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.__class__.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path )

    def get_id( self, out, err ):
        """
        Extract the job submit ID from job submission command
        output. For PBS jobs the submission command returns
        the process ID to stdout.
        """
        return out.strip()

    def get_job_poll_command( self, jid ):
        """
        Given the job submit ID, return a command string that uses
        'cylc get-task-status' (on the task host) to determine current
        job status:
           cylc get-job-status <QUEUED> <RUNNING>
        where:
            QUEUED  = true if job is waiting or running, else false
            RUNNING = true if job is running, else false

        WARNING: 'cylc get-task-status' prints a task status message -
        the final result - to stdout, so any stdout from scripting prior
        to the call must be dumped to /dev/null.

        PBS has MANY possible job states; I think we only need:
          * 'Q' (queueing) = waiting in the pbs queue
          * 'R' (running) = running
        """
        cmd = ( "RUNNING=false; QUEUED=false; "
                + "qstat -J " + jid + " | grep " + jid
                + " | awk \"{ print \$5}\" | egrep \"^R$\" > /dev/null; "
                + "[[ $? == 0 ]] && RUNNING=true && QUEUED=true; "
                + "if ! $QUEUED; then "
                + "  qstat -J " + jid + " | grep " + jid
                + "   | awk \"{ print \$5 }\" | egrep \"^Q$\" > /dev/null; "
                + "  [[ $? == 0 ]] && QUEUED=true; "
                + "fi; "
            + " cylc get-task-status " + self.jobfile_path + ".status $QUEUED $RUNNING" )
        return cmd

    def get_job_kill_command( self, jid ):
        """
        Given the job submit ID, return a command to kill the job.
        """
        cmd = "qdel " + jid
        return cmd

