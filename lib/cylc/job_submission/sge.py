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
from subprocess import check_call, Popen, PIPE

class sge( job_submit ):

    "SGE qsub job submission"

    COMMAND_TEMPLATE = "qsub %s"
    REC_ID = re.compile(r"\D+(?P<id>\d+)\D+")

    def set_directives( self ):
        self.jobconfig['directive prefix'] = "#$"
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
        output.
        """
        for line in str(out).splitlines():
            match = self.REC_ID.match(line)
            if match:
                return match.group("id")

    def kill( self, jid, st_file=None ):
        """Kill the job."""
        check_call(["qdel", jid])

    def poll( self, jid ):
        """Return 0 if jid is in the queueing system, 1 otherwise."""
        proc = Popen(["qstat", "-j", jid], stdout=PIPE)
        if proc.wait():
            return 1
        out, err = proc.communicate()
        # "qstat ID" returns something like:
        #     job-ID  prior ...
        #     ------------- ...
        #      304 0.60500  ...
        for line in out.splitlines():
            items = line.strip().split(None, 1)
            if items and (items[0] == jid or items[0].startswith(jid + ".")):
                return 0
        return 1
