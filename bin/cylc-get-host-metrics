#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA
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

"""cylc get-host-metrics [OPTIONS]

Get metrics for localhost, in the form of a JSON structure with top-level
keys as requested via the OPTIONS:

1. --load
       1, 5 and 15 minute load averages (as keys) from the 'uptime' command.
2. --memory
       Total free RAM memory, in kilobytes, from the 'free -k' command.
3. --disk-space=PATH / --disk-space=PATH1,PATH2,PATH3 (etc)
       Available disk space from the 'df -Pk' command, in kilobytes, for one
       or more valid mount directory PATHs (as listed under 'Mounted on')
       within the filesystem of localhost. Multiple PATH options can be
       specified via a comma-delimited list, each becoming a key under the
       top-level disk space key.

If no options are specified, --load and --memory are invoked by default.
"""

import sys
if '--use-ssh' in sys.argv[1:]:
    sys.argv.remove('--use-ssh')
    from cylc.flow.remote import remrun
    if remrun():
        sys.exit(0)

import re
from subprocess import Popen, PIPE, CalledProcessError, DEVNULL
import json

from cylc.flow.option_parsers import OptionParser
from cylc.flow.terminal import cli_function


"""Templates for extracting desired metric data via regular expression.

Example command outputs, with '*' enclosing data to extract with templates:

LOAD_TEMPLATES:
    $ uptime
    17:52:58 up  8:08,  2 users,  load average: *0.13*, *0.09*, *0.07*

DISK_TEMPLATES, e.g. for mount directory path option '--disk-space=/boot':
    $ df -Pk /boot
    Filesystem            1024-blocks      Used Available Capacity Mounted on
    /dev/md0                    96978     33904   *57856*      37% /boot.
"""
LOAD_TEMPLATES = [['uptime'], (1, 5, 15), re.compile(
                  r'load average:\s([\d.]+),\s([\d.]+),\s([\d.]+)')]
DISK_TEMPLATES = [['df', '-Pk'], re.compile(
                  r'Mounted on\n\S+\s+\d+\s+\d+\s+(\d+)\s+')]


def get_option_parser():
    parser = OptionParser(__doc__)

    parser.add_option(
        "--load", "-l",
        help="1, 5 and 15 minute load averages from the 'uptime' command.",
        action="store_true", default=False, dest="load")

    parser.add_option(
        "--memory", "-m",
        help="Total memory not in use by the system, buffer or cache, in " +
             "KB, from '/proc/meminfo'.",
        action="store_true", default=False, dest="memory")

    parser.add_option(
        "--disk-space",
        help="Available disk space, in KB, from the 'df -Pk' command.",
        action="store", default=None, dest="disk")

    return parser


@cli_function(get_option_parser)
def main(parser, options):
    print(get_host_metric(options.load, options.memory, options.disk))
    sys.exit()


def run_command(cmd):
    """Return the result from running a command string in a local shell.

    Return stdout if command successful, else raise CalledProcessError.
    """
    # Note: can replace function w/ 'subprocess.check_output()' when drop v2.6.
    process = Popen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
    stdout, stderr = [f.decode() for f in process.communicate()]
    return_code = process.returncode
    if return_code:
        raise CalledProcessError(
            return_code,
            ' '.join(cmd),
            stderr=stderr
        )
    else:
        return stdout


def extract_pattern(data_pattern, raw_string):
    """Try to return first parenthesized subgroup of a regex string search."""
    error_msg = "No 're.search' matches for:\n  %s\non the string:\n  %s" % (
        data_pattern.pattern, raw_string)
    try:
        matches = re.search(data_pattern, raw_string)
    except re.error:
        sys.stderr.write(error_msg)
    if matches:
        return matches.groups()
    else:
        raise AttributeError(error_msg)


def process_load():
    """Return dictionary with load average float values from 'uptime' command.

    String keys e.g. 'load:1' give minutes average was measured over.
    """
    cmd, av_times, patt = LOAD_TEMPLATES
    av_raw_tuple = extract_pattern(patt, run_command(cmd))
    av_floats_tuple = [float(av_raw) for av_raw in av_raw_tuple]
    return dict(zip(
        ["load:" + str(time) for time in av_times], av_floats_tuple))


def process_memory():
    """Return available memory.

    Note the `free` command is inconsistent accross Linux distros.

    Extracts the `MemAvailable` field from `/proc/meminfo` if present else
    returns the sum of `MemFree`, `Buffers` and `Cached`.

    ('free -k' command inconsistent across Linux distros, see e.g.
     'https://access.redhat.com/solutions/406773', so check '/proc' directly)

    """
    stdout = run_command(['cat', '/proc/meminfo'])
    fields = dict((
        line.split()[:2]
        for line in stdout.splitlines()
    ))
    try:
        mem = int(fields['MemAvailable:'])
    except KeyError:
        # fallback for older kernels - provide our own estimate
        # see: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
        #      linux.git/commit/?id=34e431b0ae398fc54ea69ff85ec700722c9da773
        mem = sum((
            int(fields['MemFree:']),
            int(fields['Buffers:']),
            int(fields['Cached:'])
        ))
    return {'memory': mem}


def process_disk(paths_list):
    """Return dictionary with available disk space for given mount dir paths.

    Disk space data, from 'df -Pk' command, stored as float values under
    associated path string keys.
    """
    cmd, patt = DISK_TEMPLATES
    path_dict = {}
    for path in paths_list:
        # Invoke 'df' for each path/file separately; safer for extracting the
        # correct data; not as efficient but the command is not intensive.
        cmd_output = run_command(cmd + [path])
        free_space_str, = extract_pattern(patt, cmd_output)
        if free_space_str:
            path_dict["disk-space:" + path] = int(free_space_str)
    return path_dict


def get_host_metric(inc_load, inc_memory, disk_paths):
    """Return JSON structure containing specified metric data for localhost.

    Example:
      {
          "load:5": 0.059999999999999998,
          "disk-space:/boot": 57856,
          "load:1": 0.050000000000000003,
          "memory": 3168296,
          "load:15": 0.080000000000000002,
          "disk-space:/": 9212088
      }

    The data included depends on the options specified to the command and
    is one or more from: load average, free memory and available disk space
    (for specified mount directory paths).
    """
    HOST_METRIC = {}

    if disk_paths:
        paths_list = disk_paths.split(',')
        # Filter out empty string from possible option spec trailing comma.
        paths_list = [path for path in paths_list if path]
        HOST_METRIC.update(process_disk(paths_list))
    # Load & memory provided as default, but disk space could be wanted
    # singly so can't just do this via the option parser defaults.
    if inc_load or all([not inc_load, not inc_memory, not disk_paths]):
        HOST_METRIC.update(process_load())
    if inc_memory or all([not inc_load, not inc_memory, not disk_paths]):
        HOST_METRIC.update(process_memory())

    return json.dumps(HOST_METRIC, indent=4)


if __name__ == "__main__":
    main()
