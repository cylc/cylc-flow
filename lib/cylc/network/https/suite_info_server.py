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
        return self._put("ping_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_cylc_version(self):
        return self._put("get_cylc_version", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_task(self, task_id, exists_only=False):
        if isinstance(exists_only, basestring):
            exists_only = ast.literal_eval(exists_only)
        return self._put("ping_task", (task_id,),
                         {"exists_only": exists_only})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_jobfile_path(self, task_id):
        return self._put("get_task_jobfile_path", (task_id,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_suite_info(self):
        return self._put("get_suite_info", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_info(self, names):
        if not isinstance(names, list):
            names = [names]
        return self._put("get_task_info", (names,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_all_families(self, exclude_root=False):
        if isinstance(exclude_root, basestring):
            exclude_root = ast.literal_eval(exclude_root)
        return self._put("get_all_families", None,
                         {"exclude_root": exclude_root})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_first_parent_descendants(self):
        return self._put("get_first_parent_descendants", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_first_parent_ancestors(self, pruned=None):
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
        if isinstance(group_nodes, basestring):
            try:
                group_nodes = ast.literal_eval(group_nodes)
            except ValueError:
                group_nodes = [group_nodes]
        if isinstance(ungroup_nodes, basestring):
            try:
                ungroup_nodes = ast.literal_eval(ungroup_nodes)
            except ValueError:
                ungroup_nodes = [ungroup_nodes]
        if isinstance(ungroup_recursive, basestring):
            ungroup_recursive = ast.literal_eval(ungroup_recursive)
        if isinstance(group_all, basestring):
            group_all = ast.literal_eval(group_all)
        if isinstance(ungroup_all, basestring):
            ungroup_all = ast.literal_eval(ungroup_all)
        if isinstance(stop_point_string, basestring):
            try:
                stop_point_string = ast.literal_eval(stop_point_string)
            except ValueError:
                pass
            else:
                if stop_point_string is not None:
                    stop_point_string = str(stop_point_string)
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
    def get_task_requisites(self, items=None, list_prereqs=False):
        if not isinstance(items, list):
            items = [items]
        return self._put("get_task_requisites", (items,),
                         {"list_prereqs": list_prereqs in [True, 'True']})

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
