#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

from cylc.suite_logging import OUT

# BROKER:
# A collection of output messages with associated owner ids (of the
# originating tasks) representing the outputs of ALL TASKS in the
# suite, and initialised from the outputs of all the tasks.
# "Satisfied" => the output has been completed.


class broker(object):
    # A broker aggregates output messages from many objects.
    # Each task registers its outputs with the suite broker, then each
    # task tries to get its prerequisites satisfied by the broker's
    # outputs.

    def __init__(self):
        self.all_outputs = {}   # all_outputs[ message ] = taskid
        self.all_output_msgs = set()

    def register(self, tasks):

        for task in tasks:
            self.all_outputs.update(task.state.outputs.completed)
            # TODO - SHOULD WE CHECK FOR SYSTEM-WIDE DUPLICATE OUTPUTS?
            # (note that successive tasks of the same type can register
            # identical outputs if they write staggered restart files).
        self.all_output_msgs = set(self.all_outputs)

    def reset(self):
        # throw away all messages
        self.all_outputs = {}
        self.all_output_msgs = set()

    def dump(self):
        # for debugging
        log_msg = "BROKER DUMP:"
        for msg in self.all_outputs:
            log_msg += "\n+ " + self.all_outputs[msg] + '\t' + msg
        OUT.info(log_msg)

    def negotiate(self, task):
        # can my outputs satisfy any of task's prerequisites
        task.state.satisfy_me(self.all_output_msgs, self.all_outputs)
