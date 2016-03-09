#!/usr/bin/env python
#############################################################################
#  
#	Run Pyro servers as daemon processes on Unix/Linux.
#	This won't work on other operating systems such as Windows.
#	Author: Jeff Bauer  (jbauer@rubic.com)
#	This software is released under the MIT software license.
#	Based on an earlier daemonize module by Jeffery Kunce
#	Updated by Luis Camaano to double-fork-detach.
#
#   DEPRECATED. Don't use this in new code.
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import sys, os, time
from signal import SIGINT

class DaemonizerException:
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

class Daemonizer:
    """
    Daemonizer is a class wrapper to run a Pyro server program
    in the background as daemon process.  The only requirement 
    is for the derived class to implement a main_loop() method.
    See Test class below for an example.

    The following command line operations are provided to support
    typical /etc/init.d startup/shutdown on Unix systems:

        start | stop | restart

    In addition, a daemonized program can be called with arguments:

        status  - check if process is still running

        debug   - run the program in non-daemon mode for testing

    Note: Since Daemonizer uses fork(), it will not work on non-Unix
    systems.
    """
    def __init__(self, pidfile=None):
        if not pidfile:
            # PID file moved out of /tmp to avoid security vulnerability
            # changed by Debian maintainer per Debian bug #631912
            self.pidfile = "/var/run/pyro-%s.pid" % self.__class__.__name__.lower()
        else:
            self.pidfile = pidfile

    def become_daemon(self, root_dir='/'):
        if os.fork() != 0:  # launch child and ...
            os._exit(0)  # kill off parent
        os.setsid()
        os.chdir(root_dir)
        os.umask(0)
        if os.fork() != 0: # fork again so we are not a session leader
            os._exit(0)
        sys.stdin.close()
        sys.__stdin__ = sys.stdin
        sys.stdout.close()
        sys.stdout = sys.__stdout__ = _NullDevice()
        sys.stderr.close()
        sys.stderr = sys.__stderr__ = _NullDevice()
        for fd in range(1024):
            try:
                os.close(fd)
            except OSError:
                pass

    def daemon_start(self, start_as_daemon=1):
        if start_as_daemon:
            self.become_daemon()
        if self.is_process_running():
            msg = "Unable to start server. Process is already running."
            raise DaemonizerException(msg)
        f = open(self.pidfile, 'w')
        f.write("%s" % os.getpid())
        f.close()
        self.main_loop()

    def daemon_stop(self):
        pid = self.get_pid()
        try:
            os.kill(pid, SIGINT)  # SIGTERM is too harsh...
            time.sleep(1)
            try:
                os.unlink(self.pidfile)
            except OSError:
                pass
        except IOError:
            pass

    def get_pid(self):
        try:
            f = open(self.pidfile)
            pid = int(f.readline().strip())
            f.close()
        except IOError:
            pid = None
        return pid

    def is_process_running(self):
        pid = self.get_pid()
        if pid:
            try:
                os.kill(pid, 0)
                return 1
            except OSError:
                pass
        return 0

    def main_loop(self):
        """NOTE: This method must be implemented in the derived class."""
        msg = "main_loop method not implemented in derived class: %s" % \
              self.__class__.__name__
        raise DaemonizerException(msg)

    def process_command_line(self, argv, verbose=1):
        usage = "usage:  %s  start | stop | restart | status | debug " \
                "[--pidfile=...] " \
                "(run as non-daemon)" % os.path.basename(argv[0])
        if len(argv) < 2:
            print usage
            raise SystemExit
        else:
            operation = argv[1]
            if len(argv) > 2 and argv[2].startswith('--pidfile=') and \
                len(argv[2]) > len('--pidfile='):
                self.pidfile = argv[2][len('--pidfile='):]
        pid = self.get_pid()
        if operation == 'status':
            if self.is_process_running():
                print "Server process %s is running." % pid
            else:
                print "Server is not running."
        elif operation == 'start':
            if self.is_process_running():
                print "Server process %s is already running." % pid
                raise SystemExit
            else:
                if verbose:
                    print "Starting server process."
                self.daemon_start()
        elif operation == 'stop':
            if self.is_process_running():
                self.daemon_stop()
                if verbose:
                    print "Server process %s stopped." % pid
            else:
                print "Server process %s is not running." % pid
                raise SystemExit
        elif operation == 'restart':
            self.daemon_stop()
            if verbose:
                print "Restarting server process."
            self.daemon_start()
        elif operation == 'debug':
            self.daemon_start(0)
        else:
            print "Unknown operation:", operation
            raise SystemExit


class _NullDevice:
    """A substitute for stdout/stderr that writes to nowhere."""
    def write(self, s):
        pass


class Test(Daemonizer):
    def __init__(self):
        Daemonizer.__init__(self)

    def main_loop(self):
        while 1:
            time.sleep(1)


if __name__ == "__main__":
    test = Test()
    test.process_command_line(sys.argv)
