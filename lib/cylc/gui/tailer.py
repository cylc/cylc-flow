#!/usr/bin/env python2

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
from cylc.gui.warning_dialog import warning_dialog


class Tailer(threading.Thread):
    """Logic to tail follow a log file for a GUI viewer.

    logview -- A GUI view to display the content of the log file.
    cmd - a given tail-follow type command.
    pollable -- If given, must implement a poll() method.

    """
    READ_SIZE = 4096
    TAGS = {
        "CRITICAL": [re.compile(r"\b(?:CRITICAL|ERROR)\b"), "red"],
        "WARNING": [re.compile(r"\bWARNING\b"), "#a83fd3"]}

    def __init__(self, logview, cmd, pollable=None, filters=None):
        super(Tailer, self).__init__()

        self.logview = logview
        self.cmd = cmd
        self.pollable = pollable
        if filters:
            self.filters = [re.compile(f) for f in filters]
        else:
            self.filters = None
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
        """Invoke the command."""
        command = shlex.split(self.cmd)
        try:
            self.proc = Popen(
                command, stdin=open(os.devnull), stdout=PIPE, stderr=STDOUT,
                preexec_fn=os.setpgrp)
        except OSError as exc:
            dialog = warning_dialog("%s: %s" % (
                exc, " ".join(quote(item) for item in command)))
            gobject.idle_add(dialog.warn)
            return

        buf = ""
        while not self.quit and self.proc.poll() is None:
            try:
                self.pollable.poll()
            except (TypeError, AttributeError):
                pass
            if (
                self.freeze or
                not select.select([self.proc.stdout.fileno()], [], [], 100)
            ):
                sleep(1)
                continue
            # Both self.proc.stdout.read(SIZE) and self.proc.stdout.readline()
            # can block. However os.read(FILENO, SIZE) should be fine after a
            # select.select().
            try:
                data = os.read(self.proc.stdout.fileno(), self.READ_SIZE)
            except (IOError, OSError) as exc:
                dialog = warning_dialog("%s: %s" % (
                    exc, " ".join(quote(item) for item in command)))
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
                            all(f.search(line) for f in self.filters)):
                        gobject.idle_add(self.update_gui, line)
            sleep(0.01)
        self.stop()

    def stop(self):
        """Stop the tailer."""
        self.quit = True
        try:
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
