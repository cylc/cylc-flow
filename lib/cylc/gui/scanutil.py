#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Scan utilities for "cylc gscan" and "cylc gpanel"."""

import os
import signal
from subprocess import Popen, PIPE, STDOUT
import sys
from time import time

import gtk

from cylc.cfgspec.gcylc import gcfg
import cylc.flags
from cylc.gui.legend import ThemeLegendWindow
from cylc.gui.util import get_icon
from cylc.network import (
    KEY_NAME, KEY_OWNER, KEY_STATES, KEY_UPDATE_TIME)
from cylc.network.port_scan import scan_all
from cylc.version import CYLC_VERSION
from cylc.wallclock import get_unix_time_from_time_string as timestr_to_seconds


DURATION_EXPIRE_STOPPED = 600.0
KEY_PORT = "port"


def get_scan_menu(suite_keys, start_func, owner=None,
                  is_stopped=False):
    """Return a right click menu for scan GUIs.

    suite_keys should be a list of (host, owner, suite) tuples (if any).
    start_func should be a function with no arguments that
    re-activates idle GUIs.
    owner (keyword) should be the owner of the suites, if not the
    current user.
    is_stopped (keyword) denotes whether the GUI is in an inactive
    state.

    """

    # TODO - what's start_func and is_stopped for?
    menu = gtk.Menu()

    if is_stopped:
        switch_on_item = gtk.ImageMenuItem("Activate")
        img = gtk.image_new_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_MENU)
        switch_on_item.set_image(img)
        switch_on_item.show()
        switch_on_item.connect("button-press-event",
                               lambda b, e: start_func())
        menu.append(switch_on_item)

    if not suite_keys:
        null_item = gtk.ImageMenuItem("Click on a suite or group")
        img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_MENU)
        null_item.set_image(img)
        null_item.show()
        menu.append(null_item)
        return menu

    # Construct gcylc launcher items for each relevant suite.
    for host, owner, suite in suite_keys:
        gcylc_item = gtk.ImageMenuItem("Launch gcylc: %s - %s@%s" % (
            suite.replace('_', '__'), owner, host))
        img_gcylc = gtk.image_new_from_stock("gcylc", gtk.ICON_SIZE_MENU)
        gcylc_item.set_image(img_gcylc)
        gcylc_item._connect_args = (host, owner, suite)
        gcylc_item.connect(
            "button-press-event",
            lambda b, e: launch_gcylc(b._connect_args))
        gcylc_item.show()
        menu.append(gcylc_item)

    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    # Construct a cylc stop item to stop a suite
    if len(suite_keys) > 1:
        stoptask_item = gtk.ImageMenuItem('Stop all...')
    else:
        stoptask_item = gtk.ImageMenuItem('Stop...')

    stop_menu = gtk.Menu()
    stoptask_item.set_submenu(stop_menu)
    img_stop = gtk.image_new_from_stock(gtk.STOCK_MEDIA_STOP,
                                        gtk.ICON_SIZE_MENU)
    stoptask_item.set_image(img_stop)

    for stop_type in ['', '--kill', '--now', '--now --now']:
        item = gtk.ImageMenuItem('stop %s' % stop_type)
        img_stop = gtk.image_new_from_stock(gtk.STOCK_MEDIA_STOP,
                                            gtk.ICON_SIZE_MENU)
        item.set_image(img_stop)
        stop_menu.append(item)
        item._connect_args = suite_keys, 'stop %s' % stop_type
        item.connect("button-press-event",
                          lambda b, e: call_cylc_command(b._connect_args[0],
                                                         b._connect_args[1]))
        item.show()

    stoptask_item.show()
    menu.append(stoptask_item)

    # Construct a cylc hold item to hold (pause) a suite
    if len(suite_keys) > 1:
        holdtask_item = gtk.ImageMenuItem('Hold all')
    else:
        holdtask_item = gtk.ImageMenuItem('Hold')

    img_hold = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
                                        gtk.ICON_SIZE_MENU)
    holdtask_item.set_image(img_hold)
    holdtask_item._connect_args = suite_keys, 'hold'
    holdtask_item.connect("button-press-event",
                          lambda b, e: call_cylc_command(b._connect_args[0],
                                                         b._connect_args[1]))
    menu.append(holdtask_item)
    holdtask_item.show()

    # Construct a cylc release item to release a paused/stopped suite
    if len(suite_keys) > 1:
        unstoptask_item = gtk.ImageMenuItem('Release all')
    else:
        unstoptask_item = gtk.ImageMenuItem('Release')

    img_release = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                                           gtk.ICON_SIZE_MENU)
    unstoptask_item.set_image(img_release)
    unstoptask_item._connect_args = suite_keys, 'release'
    unstoptask_item.connect("button-press-event",
                            lambda b, e: call_cylc_command(b._connect_args[0],
                                                           b._connect_args[1]))
    unstoptask_item.show()
    menu.append(unstoptask_item)

    return menu


def launch_about_dialog(program_name, hosts):
    """Launch a modified version of the app_main.py About dialog."""
    hosts_text = "Hosts monitored: " + ", ".join(hosts)
    comments_text = hosts_text
    about = gtk.AboutDialog()
    if gtk.gtk_version[0] == 2 and gtk.gtk_version[1] >= 12:
        # set_program_name() was added in PyGTK 2.12
        about.set_program_name(program_name)
    else:
        comments_text = program_name + "\n" + hosts_text

    about.set_version(CYLC_VERSION)
    about.set_copyright("Copyright (C) 2008-2017 NIWA")
    about.set_comments(comments_text)
    about.set_icon(get_icon())
    about.run()
    about.destroy()


def launch_hosts_dialog(existing_hosts, change_hosts_func):
    """Launch a dialog for configuring the suite hosts to scan.

    Arguments:
    existing_hosts should be a list of currently scanned host names.
    change_hosts_func should be a function accepting a new list of
    host names to scan.

    """
    dialog = gtk.Dialog()
    dialog.set_icon(get_icon())
    dialog.vbox.set_border_width(5)
    dialog.set_title("Configure suite hosts")
    dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    dialog.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
    label = gtk.Label("Enter a comma-delimited list of suite hosts to scan")
    label.show()
    label_hbox = gtk.HBox()
    label_hbox.pack_start(label, expand=False, fill=False)
    label_hbox.show()
    entry = gtk.Entry()
    entry.set_text(", ".join(existing_hosts))
    entry.connect("activate", lambda e: dialog.response(gtk.RESPONSE_OK))
    entry.show()
    dialog.vbox.pack_start(label_hbox, expand=False, fill=False, padding=5)
    dialog.vbox.pack_start(entry, expand=False, fill=False, padding=5)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        new_hosts = [h.strip() for h in entry.get_text().split(",")]
        change_hosts_func(new_hosts)
    dialog.destroy()


def get_suite_version(args):
    """Gets the suite version given the host, owner, and suite arguments"""
    f_null = open(os.devnull, "w")
    if cylc.flags.debug:
        stderr = sys.stderr
        args = ["--debug"] + args
    else:
        stderr = f_null
    command = ["cylc", "get-suite-version"] + args
    proc = Popen(command, stdout=PIPE, stderr=stderr)
    suite_version = proc.communicate()[0].strip()
    proc.wait()

    return suite_version


def launch_gcylc(key):
    """Launch gcylc for a given suite and host."""
    host, owner, suite = key
    args = ["--host=" + host, "--user=" + owner, suite]

    # Get version of suite - now separate method get_suite_version()
    f_null = open(os.devnull, "w")
    suite_version = get_suite_version(args)

    # Run correct version of "cylc gui", provided that "admin/cylc-wrapper" is
    # installed.
    env = None
    if suite_version != CYLC_VERSION:
        env = dict(os.environ)
        env["CYLC_VERSION"] = suite_version
    command = ["cylc", "gui"] + args
    if cylc.flags.debug:
        stdout = sys.stdout
        stderr = sys.stderr
        Popen(command, env=env, stdout=stdout, stderr=stderr)
    else:
        stdout = f_null
        stderr = STDOUT
        Popen(["nohup"] + command, env=env, stdout=stdout, stderr=stderr)


def call_cylc_command(keys, command_id):
    """Calls one of the Cylc commands (such as 'stop', 'hold', etc...).

    Will accept either a single tuple for a key, or a list of keys.
    See the examples below. If you pass it a list of keys, it will
    iterate and call the command_id on each suite (key) it is given.

    Args:
        keys (tuple): The key containing host, owner, and suite
        command_id (str): A string giving the Cylc command.

    Example:
        call_cylc_command(keys, "stop")
        call_cylc_command((host, owner, suite), "hold")
        call_cylc_command([(host, owner, suite),
                           (host, owner, suite),
                           (host, owner, suite)], "hold")
    """

    if not isinstance(keys, list):
        keys = [keys]

    for key in keys:
        host, owner, suite = key
        args = ["--host=" + host, "--user=" + owner, suite]

        # Get version of suite
        f_null = open(os.devnull, "w")
        suite_version = get_suite_version(args)

        env = None
        if suite_version != CYLC_VERSION:
            env = dict(os.environ)
            env["CYLC_VERSION"] = suite_version
        command = ["cylc"] + command_id.split() + args

        if cylc.flags.debug:
            stdout = sys.stdout
            stderr = sys.stderr
            Popen(command, env=env, stdout=stdout, stderr=stderr)
        else:
            stdout = f_null
            stderr = stdout
            Popen(["nohup"] + command, env=env, stdout=stdout, stderr=stderr)


def update_suites_info(
        hosts=None, timeout=None, owner_pattern=None, name_pattern=None,
        prev_results=None):
    """Return mapping of suite info by host, owner and suite name.

    hosts - hosts to scan, or the default set in the site/user global.rc
    timeout - communication timeout
    owner_pattern - return only suites with owners matching this compiled re
    name_pattern - return only suites with names matching this compiled re
    prev_results - previous results returned by this function

    Return a dict of the form: {(host, owner, name): suite_info, ...}

    where each "suite_info" is a dict with keys:
        KEY_GROUP - group name of suite
        KEY_OWNER - suite owner name
        KEY_PORT - suite port, for running suites only
        KEY_STATES - suite state
        KEY_STATES:cycle - states by cycle
        KEY_TASKS_BY_STATE - tasks by state
        KEY_TITLE - suite title
        KEY_UPDATE_TIME - last update time of suite
    """
    results = {}
    for host, port, result in scan_all(hosts=hosts, timeout=timeout):
        if (name_pattern and not name_pattern.match(result[KEY_NAME]) or
                owner_pattern and not owner_pattern.match(result[KEY_OWNER])):
            continue
        try:
            result[KEY_PORT] = port
            results[(host, result[KEY_OWNER], result[KEY_NAME])] = result
            result[KEY_UPDATE_TIME] = int(float(result[KEY_UPDATE_TIME]))
        except (KeyError, TypeError, ValueError):
            pass
    expire_threshold = time() - DURATION_EXPIRE_STOPPED
    for (host, owner, name), prev_result in prev_results.items():
        if ((host, owner, name) in results or
                host not in hosts or
                owner_pattern and not owner_pattern.match(owner) or
                name_pattern and not name_pattern.match(name)):
            # OK if suite already in current results set.
            # Don't bother if:
            # * previous host not in current hosts list
            # * previous owner does not match current owner pattern
            # * previous suite name does not match current name pattern
            continue
        if prev_result.get(KEY_PORT):
            # A previously running suite is no longer running.
            # Get suite info with "cat-state", if possible, and include in the
            # results set.
            try:
                prev_result = _update_stopped_suite_info((host, owner, name))
            except (IndexError, TypeError, ValueError):
                continue
        if prev_result.get(KEY_UPDATE_TIME, 0) > expire_threshold:
            results[(host, owner, name)] = prev_result
    return results


def _update_stopped_suite_info(key):
    """Return a map like cylc scan --raw for states and last update time."""
    host, owner, suite = key
    cmd = ["cylc", "ls-checkpoints"]
    if host:
        cmd.append("--host=" + host)
    if owner:
        cmd.append("--user=" + owner)
    if cylc.flags.debug:
        stderr = sys.stderr
        cmd.append("--debug")
    else:
        stderr = PIPE
    cmd += [suite, "0"]  # checkpoint 0 is latest checkpoint
    result = {}
    try:
        proc = Popen(cmd, stderr=stderr, stdout=PIPE, preexec_fn=os.setpgrp)
    except OSError:
        return result
    else:
        out, err = proc.communicate()
        if proc.wait():  # non-zero return code
            if cylc.flags.debug:
                sys.stderr.write(err)
            return result
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
    cur = None
    for line in out.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            cur = line
        elif cur == "# CHECKPOINT ID (ID|TIME|EVENT)":
            result = {
                KEY_UPDATE_TIME: timestr_to_seconds(line.split("|")[1]),
                KEY_STATES: ({}, {})}
        elif cur == "# TASK POOL (CYCLE|NAME|SPAWNED|STATUS|HOLD_SWAP)":
            point, _, _, state, _ = line.split("|")
            # Total count of a state
            result[KEY_STATES][0].setdefault(state, 0)
            result[KEY_STATES][0][state] += 1
            # Count of a state per cycle
            try:
                point = int(point)  # Allow integer sort, if possible
            except ValueError:
                pass
            result[KEY_STATES][1].setdefault(point, {})
            result[KEY_STATES][1][point].setdefault(state, 0)
            result[KEY_STATES][1][point][state] += 1
    return result
