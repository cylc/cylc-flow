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

from job_submit import job_submit

class background( job_submit ):

    """Run the task job script directly in a background shell.

    In contrast to job submission methods that return a "job submission
    ID" to a batch queue system (pbs, loadleveler, ...) and then detach
    immediately, background 'submission' actually runs the task directly.
    We could make it detach immediately by backgrounding with '&', but 
    this is a problem for remote background jobs at sites that do not
    allow unattended jobs on login nodes. Consequently we background
    with '&' to allow returning the PID in stdout with 'echo $!' but
    then use 'wait' to prevent exit before the job is finished:
      % ssh user@host 'job-script & echo $!; wait'
    (We have to override the general command templates to achieve this)."""

    LOCAL_COMMAND_TEMPLATE = "(%(command)s & echo $!; wait )"
    REMOTE_COMMAND_TEMPLATE = ( " '"
            + "test -f /etc/profile && . /etc/profile 1>/dev/null 2>&1;"
            + "test -f $HOME/.profile && . $HOME/.profile 1>/dev/null 2>&1;"
            + " mkdir -p $(dirname %(jobfile_path)s)"
            + " && cat >%(jobfile_path)s"
            + " && chmod +x %(jobfile_path)s" 
            + " && ( (%(command)s) & echo $!; wait )"
            + "'" )
 
    COMMAND_TEMPLATE = "%s </dev/null 1>%s 2>%s"

    def construct_jobfile_submission_command( self ):
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.__class__.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path,
                                            self.stdout_file,
                                            self.stderr_file )

    def get_id( self, pid, out, err ):
        # (see commments above)
        return out.strip()

