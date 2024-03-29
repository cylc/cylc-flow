#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from time import sleep
from cylc.flow.job_runner_handlers.background import BgCommandHandler


class DelayedBgCommandHandler(BgCommandHandler):

    @classmethod
    def submit(cls, job_file_path, submit_opts):
        result = super().submit(job_file_path, submit_opts)
        sleep(10)
        return result


JOB_RUNNER_HANDLER = DelayedBgCommandHandler()
