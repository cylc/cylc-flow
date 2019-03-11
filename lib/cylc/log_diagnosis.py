#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import re
from difflib import unified_diff


from cylc import LOG
from cylc.exceptions import LogAnalyserError


class LogSpec(object):
    """Get important information from an existing reference run log
    file, in order to do the same run for a reference test. Currently
    just gets the start and stop cycle points."""

    def __init__(self, log):
        h = open(log, 'r')
        self.lines = h.readlines()
        h.close()

    def get_initial_point_string(self):
        found = False
        for line in self.lines:
            m = re.search('Initial point: (.*)$', line)
            if m:
                found = True
                point_string = m.groups()[0]
                if point_string == "None":
                    point_string = None
                break
        if found:
            return point_string
        else:
            raise LogAnalyserError("logged start point not found")

    def get_start_point_string(self):
        found = False
        for line in self.lines:
            m = re.search('Start point: (.*)$', line)
            if m:
                found = True
                point_string = m.groups()[0]
                if point_string == "None":
                    point_string = None
                break
        if found:
            return point_string
        return None

    def get_final_point_string(self):
        found = False
        for line in self.lines:
            m = re.search('Final point: (.*)$', line)
            if m:
                found = True
                point_string = m.groups()[0]
                if point_string == "None":
                    return None
                break
        if found:
            return point_string
        else:
            raise LogAnalyserError("logged stop point not found")


class LogAnalyser(object):
    """Compare an existing reference log with the log from a new
    reference test run. Currently just compares triggering info."""

    def __init__(self, new_log, ref_log):
        h = open(new_log, 'r')
        self.new_loglines = h.readlines()
        h.close()
        h = open(ref_log, 'r')
        self.ref_loglines = h.readlines()
        h.close()

    @staticmethod
    def get_triggered(lines):
        res = []
        for line in lines:
            m = re.search(r'INFO - (\[.* -triggered off .*)$', line)
            if m:
                res.append(m.groups()[0])
        return res

    def verify_triggering(self):
        new = self.get_triggered(self.new_loglines)
        ref = self.get_triggered(self.ref_loglines)

        if len(new) == 0:
            raise LogAnalyserError(
                "new log contains no triggering info.")

        if len(ref) == 0:
            raise LogAnalyserError(
                "reference log contains no triggering info.")

        new.sort()
        ref.sort()

        if new != ref:
            diff = unified_diff(new, ref, 'this run', 'reference log')
            raise LogAnalyserError(
                "triggering is NOT consistent with the reference log:" +
                '\n' + '\n'.join(diff) + '\n')
        else:
            LOG.info(
                "LogAnalyser: triggering is consistent with the reference log")
