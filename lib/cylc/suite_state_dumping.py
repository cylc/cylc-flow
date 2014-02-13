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

from datetime import datetime
import errno
import os
from global_config import get_global_cfg

class dumper( object ):

    BASE_NAME = 'state'

    def __init__( self, suite, run_mode='live', clock=None, ict=None, stop_tag=None ):
        self.run_mode = run_mode
        self.clock = clock
        self.set_cts(ict, stop_tag)
        gcfg = get_global_cfg()
        self.dir_name = gcfg.get_derived_host_item( suite,
                                                    'suite state directory' )
        self.file_name = os.path.join( self.dir_name, self.BASE_NAME )
        self.arch_len = gcfg.cfg[ 'state dump rolling archive length' ]
        if not self.arch_len or int(self.arch_len) <= 1:
            self.arch_len = 1
        self.arch_files = []
        self.pool = None
        self.wireless = None

    def set_cts( self, ict, fct ):
        self.ict = ict
        self.stop_tag = fct

        self.cts_str = ""
        if self.ict:
            self.cts_str += 'initial cycle : ' + self.ict + '\n'
        else:
            self.cts_str += 'initial cycle : (none)\n'

        if self.stop_tag:
            self.cts_str += 'final cycle : ' + self.stop_tag + '\n'
        else:
            self.cts_str += 'final cycle : (none)\n'

    def dump( self, tasks=None, wireless=None ):
        """Dump suite states to disk. Return state file basename on success."""

        tag = datetime.utcnow().strftime("%Y%m%dT%H%M%S.%fZ")
        base_name = self.BASE_NAME + "." + tag
        handle = open(os.path.join(self.dir_name, base_name), "wb")

        # suite time
        if self.run_mode == 'live':
            handle.write( 'suite time : ' + self.clock.dump_to_str() + '\n' )
        else:
            handle.write( 'simulation time : ' + self.clock.dump_to_str() +
                          ',' + str( self.clock.get_rate()) + '\n' )

        handle.write(self.cts_str)

        if wireless is None:
            wireless = self.wireless
        if wireless is not None:
            wireless.dump(handle)

        handle.write( 'Begin task states\n' )

        if tasks is None and self.pool is not None:
            tasks = self.pool.get_tasks()
        if tasks is not None:
            for itask in sorted(tasks, key=lambda t: t.id):
                # TODO - CHECK THIS STILL WORKS
                itask.dump_class_vars( handle )
                # task instance variables
                itask.dump_state( handle )

        os.fsync(handle.fileno())
        handle.close()

        # Point "state" symbolic link to new dated state dump
        try:
            os.unlink(self.file_name)
        except OSError as x:
            if x.errno != errno.ENOENT:
                raise
        os.symlink(base_name, self.file_name)
        self.arch_files.append(handle.name)
        # Remove state dump older than archive length
        while len(self.arch_files) > self.arch_len:
            try:
                os.unlink(self.arch_files.pop(0))
            except OSError as x:
                if x.errno != errno.ENOENT:
                    raise
        return base_name
