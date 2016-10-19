#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import ast
import sys

import cylc.flags
from cylc.network.https.base_server import BaseCommsServer
from cylc.network import check_access_priv

import cherrypy


class SuiteInfoServer(BaseCommsServer):
    """Server-side suite information interface."""

    def __init__(self, info_commands):
        super(SuiteInfoServer, self).__init__()
        self.commands = info_commands

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_suite(self):
        """Return True if the suite is alive!

        Example URL:

        * /ping_suite

        """
        return self._put("ping_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_cylc_version(self):
        """Return the cylc version used to run this suite."""
        return self._put("get_cylc_version", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_task(self, task_id, exists_only=False):
        """Return True if task exists and is running.

        Example URL:

        * /ping_task?task_id=foo.1
        * /ping_task?task_id=foo.2&exists_only=True

        Args:

        * task_id - string
            task_id should be the task to ping.

        Kwargs:

        * exists_only - boolean
            exists_only, if True, means that the task
            does not need to be running for this method
            to return True - it only needs to exist.

        """
        if isinstance(exists_only, basestring):
            exists_only = ast.literal_eval(exists_only)
        return self._put("ping_task", (task_id,),
                         {"exists_only": exists_only})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_jobfile_path(self, task_id):
        """Return the path to the task job script for task_id.

        Example URL:

        * /get_task_jobfile_path?task_id=foo.1

        Args:

        * task_id - string
            task_id should be the task to get the job file for.

        """
        return self._put("get_task_jobfile_path", (task_id,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_suite_info(self):
        """Return a dict with key-values for suite title and description.

        Example URL:

        * /get_suite_info

        """
        return self._put("get_suite_info", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_info(self, name):
        """Return a dict with key-values for task title and description.

        Example URL:

        * /get_task_info?name=foo

        """
        return self._put("get_task_info", (name,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_all_families(self, exclude_root=False):
        """Return a list of all families.

        Example URLs:

        * /get_all_families
        * /get_all_families?exclude_root=True

        Kwargs:

        * exclude_root - boolean
            if exclude_root is True, do not include 'root' in the list.

        """
        if isinstance(exclude_root, basestring):
            exclude_root = ast.literal_eval(exclude_root)
        return self._put("get_all_families", None,
                         {"exclude_root": exclude_root})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_first_parent_descendants(self):
        """Return a dict of families (keys) vs descendant lists (values).

        Example URL:

        * /get_first_parent_descendants

        """
        return self._put("get_first_parent_descendants", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_first_parent_ancestors(self, pruned=False):
        """Return a dict of families (keys) vs ancestor lists (values).

        Example URL:

        * /get_first_parent_ancestors
        * /get_first_parent_ancestors?pruned=True

        Kwargs:

        * pruned - boolean
            If True, prune non-task namespaces from ancestors dict.

        """
        if isinstance(pruned, basestring):
            pruned = ast.literal_eval(pruned)
        return self._put("get_first_parent_ancestors", None,
                         {"pruned": pruned})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_graph_raw(self, start_point_string, stop_point_string,
                      group_nodes=None, ungroup_nodes=None,
                      ungroup_recursive=False, group_all=False,
                      ungroup_all=False):
        """Return a list of graph edges for this suite.

        Example URLs:

        * /get_graph_raw?start_point_string=20160101T0000Z&stop_point_string=20160501T0000Z
        * /get_graph_raw?start_point_string=10&stop_point_string=20&group_all=True

        Args:

        * start_point_string - string
            This should be the cycle point to begin graphing with.
        * stop_point_string - string
            This should be the cycle point to end graphing with.

        Kwargs:

        * group_nodes - list or None
            This should be the list of custom nodes to 'group up'.
        * ungroup_nodes - list or None
            This should be the list of custom nodes to 'ungroup'.
        * ungroup_recursive - boolean
            If True and ungroup_nodes is given, recursively ungroup
            those nodes.
        * group_all - boolean
            If True, group all tasks and families up to the highest
            non-root level possible.
        * ungroup_all - boolean
            If True, ungroup all families so that only task edges are
            present.

        """
        if isinstance(group_nodes, basestring):
            group_nodes = ast.literal_eval(group_nodes)
        if isinstance(ungroup_nodes, basestring):
            ungroup_nodes = ast.literal_eval(ungroup_nodes)
        if isinstance(ungroup_recursive, basestring):
            ungroup_recursive = ast.literal_eval(ungroup_recursive)
        if isinstance(group_all, basestring):
            group_all = ast.literal_eval(group_all)
        if isinstance(ungroup_all, basestring):
            ungroup_all = ast.literal_eval(ungroup_all)
        return self._put(
            "get_graph_raw", (start_point_string, stop_point_string),
            {"group_nodes": group_nodes,
             "ungroup_nodes": ungroup_nodes,
             "ungroup_recursive": ungroup_recursive,
             "group_all": group_all,
             "ungroup_all": ungroup_all}
        )

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_requisites(self, name, point_string):
        """Get task requisites for task name at point_string.

        Example URL:

        * /get_task_requisites?name=foo&point_string=20161201T0000Z

        Args:

        * name - string
            name of the task, excluding cycle point
        * point_string - string
            cycle point of the task.

        """
        return self._put("get_task_requisites", (name, point_string))

    def _put(self, command, command_args, command_kwargs=None):
        if command_args is None:
            command_args = tuple()
        if command_kwargs is None:
            command_kwargs = {}
        if ('ping' in command or 'version' in command):
            # Free info.
            pass
        elif 'suite' in command and 'info' in command:
            # Suite title and description only.
            check_access_priv(self, 'description')
        else:
            check_access_priv(self, 'full-read')
        self.report(command)
        return self.commands[command](*command_args, **command_kwargs)
