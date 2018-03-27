#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
import re
import signal
from subprocess import Popen, PIPE, STDOUT
import sys
from time import time

import gtk

from cylc.cfgspec.gcylc import gcfg
import cylc.flags
from cylc.gui.legend import ThemeLegendWindow
from cylc.gui.util import get_icon
from cylc.hostuserutil import get_user
from cylc.network.port_scan import (
    get_scan_items_from_fs, scan_many, DEBUG_DELIM)
from cylc.suite_status import (
    KEY_NAME, KEY_OWNER, KEY_STATES, KEY_UPDATE_TIME)
from cylc.version import CYLC_VERSION
from cylc.wallclock import get_unix_time_from_time_string as timestr_to_seconds


DURATION_EXPIRE_STOPPED = 600.0
KEY_PORT = "port"
DEBUG_DELIM = '\n' + ' ' * 4


def get_gpanel_scan_menu(
        suite_keys, theme_name, set_theme_func, has_stopped_suites,
        clear_stopped_suites_func, scanned_hosts, change_hosts_func,
        update_now_func, start_func, program_name, extra_items=None,
        owner=None, is_stopped=False):
    """Return a right click menu for the gpanel GUI.

    TODO this used to be for gscan too; simplify now it's only for gpanel?

    suite_keys should be a list of (host, owner, suite) tuples (if any).
    theme_name should be the name of the current theme.
    set_theme_func should be a function accepting a new theme name.
    has_stopped_suites should be a boolean denoting currently
    stopped suites.
    clear_stopped_suites should be a function with no arguments that
    removes stopped suites from the current view.
    scanned_hosts should be a list of currently scanned suite hosts.
    change_hosts_func should be a function accepting a new list of
    suite hosts to scan.
    update_now_func should be a function with no arguments that
    forces an update now or soon.
    start_func should be a function with no arguments that
    re-activates idle GUIs.
    program_name should be a string describing the parent program.
    extra_items (keyword) should be a list of extra menu items to add
    to the right click menu.
    owner (keyword) should be the owner of the suites, if not the
    current user.
    is_stopped (keyword) denotes whether the GUI is in an inactive
    state.

    """
    menu = gtk.Menu()

    if is_stopped:
        switch_on_item = gtk.ImageMenuItem("Activate")
        img = gtk.image_new_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_MENU)
        switch_on_item.set_image(img)
        switch_on_item.show()
        switch_on_item.connect("button-press-event",
                               lambda b, e: start_func())
        menu.append(switch_on_item)

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
    if suite_keys:
        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()
        menu.append(sep_item)

    if extra_items is not None:
        for item in extra_items:
            menu.append(item)
        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()
        menu.append(sep_item)

    # Construct a cylc stop item to stop a suite
    if len(suite_keys) > 1:
        stoptask_item = gtk.ImageMenuItem('Stop all')
    else:
        stoptask_item = gtk.ImageMenuItem('Stop')

    img_stop = gtk.image_new_from_stock(gtk.STOCK_MEDIA_STOP,
                                        gtk.ICON_SIZE_MENU)
    stoptask_item.set_image(img_stop)
    stoptask_item._connect_args = suite_keys, 'stop'
    stoptask_item.connect("button-press-event",
                          lambda b, e: call_cylc_command(b._connect_args[0],
                                                         b._connect_args[1]))
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

    # Add another separator
    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    # Construct theme chooser items (same as cylc.gui.app_main).
    theme_item = gtk.ImageMenuItem('Theme')
    img = gtk.image_new_from_stock(gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
    theme_item.set_image(img)
    theme_item.set_sensitive(not is_stopped)
    thememenu = gtk.Menu()
    theme_item.set_submenu(thememenu)
    theme_item.show()

    theme_items = {}
    theme = "default"
    theme_items[theme] = gtk.RadioMenuItem(label=theme)
    thememenu.append(theme_items[theme])
    theme_items[theme].theme_name = theme
    for theme in gcfg.get(['themes']):
        if theme == "default":
            continue
        theme_items[theme] = gtk.RadioMenuItem(
            group=theme_items['default'], label=theme)
        thememenu.append(theme_items[theme])
        theme_items[theme].theme_name = theme

    # set_active then connect, to avoid causing an unnecessary toggle now.
    theme_items[theme_name].set_active(True)
    for theme in gcfg.get(['themes']):
        theme_items[theme].show()
        theme_items[theme].connect(
            'toggled',
            lambda i: (i.get_active() and set_theme_func(i.theme_name)))

    menu.append(theme_item)
    theme_legend_item = gtk.MenuItem("Show task state key")
    theme_legend_item.show()
    theme_legend_item.set_sensitive(not is_stopped)
    theme_legend_item.connect(
        "button-press-event",
        lambda b, e: ThemeLegendWindow(None, gcfg.get(['themes', theme_name]))
    )
    menu.append(theme_legend_item)
    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    # Construct a trigger update item.
    update_now_item = gtk.ImageMenuItem("Update Now")
    img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
    update_now_item.set_image(img)
    update_now_item.show()
    update_now_item.set_sensitive(not is_stopped)
    update_now_item.connect("button-press-event",
                            lambda b, e: update_now_func())
    menu.append(update_now_item)

    # Construct a clean stopped suites item.
    clear_item = gtk.ImageMenuItem("Clear Stopped Suites")
    img = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)
    clear_item.set_image(img)
    clear_item.show()
    clear_item.set_sensitive(has_stopped_suites)
    clear_item.connect("button-press-event",
                       lambda b, e: clear_stopped_suites_func())
    menu.append(clear_item)

    # Construct a configure scanned hosts item.
    hosts_item = gtk.ImageMenuItem("Configure Hosts")
    img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
    hosts_item.set_image(img)
    hosts_item.show()
    hosts_item.connect(
        "button-press-event",
        lambda b, e: launch_hosts_dialog(scanned_hosts, change_hosts_func))
    menu.append(hosts_item)

    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    # Construct an about dialog item.
    info_item = gtk.ImageMenuItem("About")
    img = gtk.image_new_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
    info_item.set_image(img)
    info_item.show()
    info_item.connect(
        "button-press-event",
        lambda b, e: launch_about_dialog(program_name, scanned_hosts)
    )
    menu.append(info_item)
    return menu


def get_scan_menu(suite_keys, toggle_hide_menu_bar):
    """Return a right click menu for the gscan GUI.

    suite_keys should be a list of (host, owner, suite) tuples (if any).
    toggle_hide_menu_bar - function to show/hide main menu bar

    """
    def _add_main_menu_item(menu):
        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()
        menu.append(sep_item)
        main_menu_item = gtk.ImageMenuItem("toggle main menu (<Alt>m)")
        img = gtk.image_new_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        main_menu_item.set_image(img)
        main_menu_item.connect("button-press-event",
                               lambda b, e: toggle_hide_menu_bar())
        main_menu_item.show()
        menu.append(main_menu_item)

    menu = gtk.Menu()

    if not suite_keys:
        null_item = gtk.ImageMenuItem("Click on a suite or group")
        img = gtk.image_new_from_stock(
            gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_MENU)
        null_item.set_image(img)
        null_item.show()
        menu.append(null_item)
        _add_main_menu_item(menu)
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
        item.connect(
            "button-press-event",
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
    _add_main_menu_item(menu)

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
    about.set_copyright("Copyright (C) 2008-2018 NIWA")
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
        change_hosts_func([h.strip() for h in entry.get_text().split(",")])
    dialog.destroy()


def get_suite_version(args):
    """Gets the suite version given the host, owner, and suite arguments"""
    if cylc.flags.debug:
        stderr = sys.stderr
        args = ["--debug"] + args
    else:
        stderr = open(os.devnull, "w")
    command = ["cylc", "get-suite-version"] + args
    proc = Popen(command, stdin=open(os.devnull), stdout=PIPE, stderr=stderr)
    suite_version = proc.communicate()[0].strip()
    proc.wait()

    return suite_version


def launch_gcylc(key):
    """Launch gcylc for a given suite and host."""
    host, owner, suite = key
    args = ["--host=" + host, "--user=" + owner, suite]

    # Get version of suite - now separate method get_suite_version()
    suite_version = get_suite_version(args)

    # Run correct version of "cylc gui", provided that "admin/cylc-wrapper" is
    # installed.
    env = None
    if suite_version != CYLC_VERSION:
        env = dict(os.environ)
        env["CYLC_VERSION"] = suite_version
    command = ["cylc", "gui"] + args
    stdin = open(os.devnull)
    if cylc.flags.debug:
        stdout = sys.stdout
        stderr = sys.stderr
    else:
        command = ["nohup"] + command
        stdout = open(os.devnull, "w")
        stderr = STDOUT
    Popen(command, env=env, stdin=stdin, stdout=stdout, stderr=stderr)


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
        suite_version = get_suite_version(args)

        env = None
        if suite_version != CYLC_VERSION:
            env = dict(os.environ)
            env["CYLC_VERSION"] = suite_version
        command = ["cylc"] + command_id.split() + args
        stdin = open(os.devnull)
        if cylc.flags.debug:
            stdout = sys.stdout
            stderr = sys.stderr
        else:
            command = ["nohup"] + command
            stdout = open(os.devnull, "w")
            stderr = stdout
        Popen(command, env=env, stdin=stdin, stdout=stdout, stderr=stderr)


def update_suites_info(updater, full_mode=False):
    """Return mapping of suite info by host, owner and suite name.

    Args:
        updater (object): gscan or gpanel updater:
            Compulsory attributes from updater:
                hosts: hosts to scan
                owner_pattern: re to filter results by owners
                suite_info_map: previous results returned by this function
            Optional attributes from updater:
                timeout: communication timeout
        full_mode (boolean): update in full mode?

    Return:
        dict: {(host, owner, name): suite_info, ...}
        where each "suite_info" is a dict with keys:
            KEY_GROUP: group name of suite
            KEY_META: suite metadata (new in 7.6)
            KEY_OWNER: suite owner name
            KEY_PORT: suite port, for running suites only
            KEY_STATES: suite state
            KEY_TASKS_BY_STATE: tasks by state
            KEY_TITLE: suite title
            KEY_UPDATE_TIME: last update time of suite
    """
    # Compulsory attributes from updater
    # hosts - hosts to scan, or the default set in the site/user global.rc
    # owner_pattern - return only suites with owners matching this compiled re
    # suite_info_map - previous results returned by this function
    # Optional attributes from updater
    # timeout - communication timeout
    owner_pattern = updater.owner_pattern
    timeout = getattr(updater, "comms_timeout", None)
    # name_pattern - return only suites with names matching this compiled re
    name_pattern = getattr(updater, "name_pattern", None)
    # Determine items to scan
    results = {}
    items = []
    if full_mode and updater.hosts:
        # Scan full port range on all hosts
        items.extend(updater.hosts)
        if owner_pattern is None:
            owner_pattern = re.compile(r"\A" + get_user() + r"\Z")
    elif full_mode:
        # Get (host, port) list from file system
        items.extend(get_scan_items_from_fs(owner_pattern, updater))
    else:
        # Scan suites in previous results only
        for (host, owner, name), prev_result in updater.suite_info_map.items():
            port = prev_result.get(KEY_PORT)
            if port:
                items.append((host, port))
            else:
                results[(host, owner, name)] = prev_result
    if not items:
        return results
    if cylc.flags.debug:
        sys.stderr.write('Scan items:%s%s\n' % (
            DEBUG_DELIM, DEBUG_DELIM.join(str(item) for item in items)))
    # Scan
    for host, port, result in scan_many(
            items, timeout=timeout, updater=updater):
        if updater.quit:
            return
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
    for (host, owner, name), prev_result in updater.suite_info_map.items():
        if updater.quit:
            return
        if ((host, owner, name) in results or
                owner_pattern and not owner_pattern.match(owner) or
                name_pattern and not name_pattern.match(name)):
            # OK if suite already in current results set.
            # Don't bother if:
            # * previous owner does not match current owner pattern
            # * previous suite name does not match current name pattern
            continue
        if prev_result.get(KEY_PORT):
            # A previously running suite is no longer running.
            # Get suite info with "ls-checkpoints", if possible, and include in
            # the results set.
            try:
                prev_result.update(
                    _update_stopped_suite_info((host, owner, name)))
                del prev_result[KEY_PORT]
            except (IndexError, TypeError, ValueError):
                continue
        if prev_result.get(KEY_UPDATE_TIME, 0) > expire_threshold:
            results[(host, owner, name)] = prev_result
    return results


def _update_stopped_suite_info(key):
    """Use "cylc ls-checkpoints" to obtain info of stopped suite."""
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
        proc = Popen(
            cmd, stdin=open(os.devnull), stderr=stderr, stdout=PIPE,
            preexec_fn=os.setpgrp)
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
