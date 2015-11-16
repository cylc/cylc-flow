#!/usr/bin/env python

import sys
import re
from difflib import unified_diff


class LogAnalyserError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class LogSpec(object):
    """Get important information from an existing reference run log
    file, in order to do the same run for a reference test. Currently
    just gets the start and stop cycle points."""

    def __init__(self, log):
        h = open(log, 'rb')
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
            raise LogAnalyserError("ERROR: logged start point not found")

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
            raise LogAnalyserError("ERROR: logged stop point not found")


class LogAnalyser(object):
    """Compare an existing reference log with the log from a new
    reference test run. Currently just compares triggering info."""

    def __init__(self, new_log, ref_log):
        h = open(new_log, 'rb')
        self.new_loglines = h.readlines()
        h.close()
        h = open(ref_log, 'rb')
        self.ref_loglines = h.readlines()
        h.close()

    def get_triggered(self, lines):
        res = []
        for line in lines:
            m = re.search('INFO - (\[.* -triggered off .*)$', line)
            if m:
                res.append(m.groups()[0])
        return res

    def verify_triggering(self):
        new = self.get_triggered(self.new_loglines)
        ref = self.get_triggered(self.ref_loglines)

        if len(new) == 0:
            raise LogAnalyserError(
                "ERROR: new log contains no triggering info.")

        if len(ref) == 0:
            raise LogAnalyserError(
                "ERROR: reference log contains no triggering info.")

        new.sort()
        ref.sort()

        if new != ref:
            diff = unified_diff(new, ref)
            print >> sys.stderr, '\n'.join(diff)
            raise LogAnalyserError(
                "ERROR: triggering is NOT consistent with the reference log")
        else:
            print(
                "LogAnalyser: triggering is consistent with the reference log")
