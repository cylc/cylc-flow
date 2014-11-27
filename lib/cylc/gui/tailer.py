#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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

import gobject
import threading, subprocess
import os, sys, re, time
from cylc import tail
from warning_dialog import warning_dialog

class tailer(threading.Thread):
    def __init__( self, logview, log, proc=None, tag=None, warning_re=None, critical_re=None ):
        super( tailer, self).__init__()
        self.logview = logview
        self.logbuffer = logview.get_buffer()
        self.logfile = log
        self.quit = False
        self.tag = tag
        self.proc = proc
        self.freeze = False
        self.warning_re = warning_re
        self.critical_re = critical_re
        self.warning_tag = self.logbuffer.create_tag( None, foreground = "#a83fd3" )
        self.critical_tag = self.logbuffer.create_tag( None, foreground = "red" )

    def clear( self ):
        s,e = self.logbuffer.get_bounds()
        self.logbuffer.delete( s,e )

    def run( self ):
        #gobject.idle_add( self.clear )
        #print "Starting tailer thread"

        if re.match( '^.+:', self.logfile ):
            # Handle remote task output statically - can't get a live
            # feed using 'ssh owner@host tail -f file' in a subprocess
            # because p.stdout.readline() blocks waiting for more output.
            #   Use shell=True in case the task owner is defined by
            # environment variable (e.g. owner=nwp_$SYS, where
            # SYS=${HOME##*_} for usernames like nwp_oper, nwp_test)
            #   But quote the remote command so that '$HOME' in it is
            # interpreted on the remote machine.
            loc, file = self.logfile.split(':')
            command = ["ssh -oBatchMode=yes " + loc + " 'cat " + file + "'"]
            try:
                p = subprocess.Popen( command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True )
            except OSError, x:
                # Probably: ssh command not found
                out = str(x)
                out += "\nERROR: failed to invoke ssh to cat the remote log file."
            else:
                # Success, or else problems reported by ssh (e.g. host
                # not found or passwordless access  not configured) go
                # to stdout/stderr.
                out = ' '.join(command) + '\n'
                out += p.communicate()[0]

                out += """
!!! gcylc WARNING: REMOTE TASK OUTPUT IS NOT LIVE, OPEN THE VIEWER AGAIN TO UPDATE !!!
"""
            gobject.idle_add( self.update_gui, out )
            if self.proc != None:
                # See comment below
                self.proc.poll()
        else:
            # Live feed (pythonic 'tail -f') for local job submission.
            #if not os.path.exists( self.logfile ):
            #    #gobject.idle_add( self.warn, "File not found: " + self.logfile )
            #    print "File not found: " + self.logfile
            #    #print "Disconnecting from tailer thread"
            #    return
            try:
                gen = tail.tail( open( self.logfile ))
            except Exception as x:
                # e.g. file not found
                dialog = warning_dialog( type(x).__name__ + ": " + str(x) )
                gobject.idle_add(dialog.warn)
                return

            while not self.quit:
                if not self.freeze:
                    line = gen.next()
                    if line:
                        gobject.idle_add( self.update_gui, line )
                if self.proc != None:
                    # poll the subprocess; this reaps its exit code and thus
                    # prevents the pid of the finished process staying in
                    # the OS process table (a "defunct process") until the
                    # parent process exits.
                    self.proc.poll()
                # The following doesn't work, not sure why, perhaps because
                # the top level subprocess finishes before the next one
                # (shows terminated too soon).
                #    if self.proc.poll() != None:
                #        (poll() returns None if process hasn't finished yet.)
                #        #print 'process terminated'
                #        gobject.idle_add( self.update_gui, '(PROCESS COMPLETED)\n' )
                #        break
            #print "Disconnecting from tailer thread"

    def update_gui( self, line ):
        if self.critical_re and re.search( self.critical_re, line ):
            self.logbuffer.insert_with_tags( self.logbuffer.get_end_iter(), line, self.critical_tag )
        elif self.warning_re and re.search( self.warning_re, line ):
            self.logbuffer.insert_with_tags( self.logbuffer.get_end_iter(), line, self.warning_tag )
        elif self.tag:
            self.logbuffer.insert_with_tags( self.logbuffer.get_end_iter(), line, self.tag )
        else:
            self.logbuffer.insert( self.logbuffer.get_end_iter(), line )
        self.logview.scroll_to_iter( self.logbuffer.get_end_iter(), 0 )
        return False
