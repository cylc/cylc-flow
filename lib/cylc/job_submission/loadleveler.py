#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
import cylc.TaskID
from subprocess import check_call, Popen, PIPE

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
        defaults[ 'job_name' ] = self.suite + cylc.TaskID.DELIM + self.task_id
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

    def set_job_vacation_signal( self ):
        """Set self.jobconfig['job vacation signal'] = 'USR1'

        (If restart=yes is defined in self.jobconfig['directives'])

        """
        if self.jobconfig['directives'].get('restart') == 'yes':
            self.jobconfig['job vacation signal'] = 'USR1'

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
        if err:
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

    def kill( self, jid, st_file=None ):
        """Kill the job."""
        check_call(["llcancel", jid])

    def poll( self, jid ):
        """Return 0 if jid is in the queueing system, 1 otherwise."""
        proc = Popen(["llq", "-f%id", jid], stdout=PIPE)
        if proc.wait():
            return 1
        out, err = proc.communicate()
        # "llq -f%id ID" returns EITHER something like:
        #     Step Id
        #     ------------------------
        #     a001.3274552.0
        #
        #     1 job step(s) in query, ...
        # OR:
        #     llq: There is currently no job status to report.
        # "jid" is in queue if it matches a stripped row.
        for line in out.splitlines():
            items = line.strip().split(None, 1)
            if items and (items[0] == jid or items[0].startswith(jid + ".")):
                return 0
        return 1
