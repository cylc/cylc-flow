#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
"""Logic to tail follow a log file for a GUI viewer."""

import gobject
import os
from pipes import quote
import re
import select
import shlex
import signal
from subprocess import Popen, PIPE, STDOUT
import threading
from time import sleep

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.gui.warning_dialog import warning_dialog


class Tailer(threading.Thread):
    """Logic to tail follow a log file for a GUI viewer.

    logview -- A GUI view to display the content of the log file.
    filename -- The name of the log file.
    cmd_tmpl -- The command template use to follow the log file.
                (global cfg '[hosts][HOST]remote/local tail command template')
    pollable -- If specified, it must implement a pollable.poll() method,
                which is called at regular intervals.
    """

    READ_SIZE = 4096
    TAGS = {
        "CRITICAL": [re.compile(r"\b(?:CRITICAL|ERROR)\b"), "red"],
        "WARNING": [re.compile(r"\bWARNING\b"), "#a83fd3"]}

    def __init__(self, logview, filename, cmd_tmpl=None, pollable=None,
                 filters=None):
        super(Tailer, self).__init__()

        self.logview = logview
        self.filename = filename
        self.cmd_tmpl = cmd_tmpl
        self.pollable = pollable
        self.filters = filters

        self.logbuffer = logview.get_buffer()
        self.quit = False
        self.proc = None
        self.freeze = False
        self.has_warned_corrupt = False
        self.tags = {}

    def clear(self):
        """Clear the log buffer."""
        pos_start, pos_end = self.logbuffer.get_bounds()
        self.logbuffer.delete(pos_start, pos_end)

    def run(self):
        """Invoke the tailer."""
        command = []
        if ":" in self.filename:  # remote
            user_at_host, filename = self.filename.split(':')
            if "@" in user_at_host:
                owner, host = user_at_host.split("@", 1)
            else:
                owner, host = (None, user_at_host)
            ssh = str(GLOBAL_CFG.get_host_item(
                "remote shell template", host, owner)).replace(" %s", "")
            command = shlex.split(ssh) + ["-n", user_at_host]
            cmd_tmpl = str(GLOBAL_CFG.get_host_item(
                "remote tail command template", host, owner))
        else:
            filename = self.filename
            cmd_tmpl = str(GLOBAL_CFG.get_host_item(
                "local tail command template"))

        if self.cmd_tmpl:
            cmd_tmpl = self.cmd_tmpl
        command += shlex.split(cmd_tmpl % {"filename": filename})
        try:
            self.proc = Popen(
                command, stdout=PIPE, stderr=STDOUT, preexec_fn=os.setpgrp)
        except OSError as exc:
            # E.g. ssh command not found
            dialog = warning_dialog("%s: %s" % (
                exc, " ".join([quote(item) for item in command])))
            gobject.idle_add(dialog.warn)
            return
        poller = select.poll()
        poller.register(self.proc.stdout.fileno())

        buf = ""
        while not self.quit and self.proc.poll() is None:
            try:
                self.pollable.poll()
            except (TypeError, AttributeError):
                pass
            if self.freeze or not poller.poll(100):  # 100 ms timeout
                sleep(1)
                continue
            # Both self.proc.stdout.read(SIZE) and self.proc.stdout.readline()
            # can block. However os.read(FILENO, SIZE) should be fine after a
            # poller.poll().
            try:
                data = os.read(self.proc.stdout.fileno(), self.READ_SIZE)
            except (IOError, OSError) as exc:
                dialog = warning_dialog("%s: %s" % (
                    exc, " ".join([quote(item) for item in command])))
                gobject.idle_add(dialog.warn)
                break
            if data:
                # Manage buffer, only add full lines to display to ensure
                # filtering and tagging work
                for line in data.splitlines(True):
                    if not line.endswith("\n"):
                        buf += line
                        continue
                    elif buf:
                        line = buf + line
                        buf = ""
                    if (not self.filters or
                            all([re.search(f, line) for f in self.filters])):
                        gobject.idle_add(self.update_gui, line)
            sleep(0.01)
        self.stop()

    def stop(self):
        """Stop the tailer."""
        self.quit = True
        try:
            # It is important that we kill processes like "tail -F", or it will
            # hang the GUI.
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait()
        except (AttributeError, OSError):
            pass

    def update_gui(self, line):
        """Update the GUI viewer."""
        try:
            line.decode('utf-8')
        except UnicodeDecodeError as exc:
            if self.has_warned_corrupt:
                return False
            self.has_warned_corrupt = True
            dialog = warning_dialog("Problem reading file:\n    %s: %s" %
                                    (type(exc).__name__, exc))
            gobject.idle_add(dialog.warn)
            return False
        for word, setting in self.TAGS.items():
            rec, colour = setting
            if rec.match(line):
                if word not in self.tags:
                    self.tags[word] = self.logbuffer.create_tag(
                        None, foreground=colour)
                self.logbuffer.insert_with_tags(
                    self.logbuffer.get_end_iter(), line, self.tags[word])
                break
        else:
            self.logbuffer.insert(self.logbuffer.get_end_iter(), line)
        self.logview.scroll_to_iter(self.logbuffer.get_end_iter(), 0)
        return False
