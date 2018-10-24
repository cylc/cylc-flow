#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""GraphQL API schema via Graphene implementation."""


import graphene
from graphene import relay
from graphene.types.resolver import dict_resolver


class ApiVersion(graphene.ObjectType):
    """Time zone info."""
    class Meta:
        default_resolver = dict_resolver
    version = graphene.Int()

class QLTimeZone(graphene.ObjectType):
    """Time zone info."""
    class Meta:
        default_resolver = dict_resolver
    hours = graphene.Int()
    string_basic = graphene.String()
    string_extended = graphene.String()
    minutes = graphene.Int()

class QLStateTotals(graphene.ObjectType):
    """State Totals."""
    class Meta:
        default_resolver = dict_resolver
    runahead = graphene.Int()
    waiting = graphene.Int()
    held = graphene.Int()
    queued = graphene.Int()
    expired = graphene.Int()
    ready = graphene.Int()
    submit_failed = graphene.Int()
    submit_retrying = graphene.Int()
    submitted = graphene.Int()
    retrying = graphene.Int()
    running = graphene.Int()
    failed = graphene.Int()
    succeeded = graphene.Int()


class QLGlobal(graphene.ObjectType):
    """Global suite info."""
    class Meta:
        default_resolver = dict_resolver

    suite = graphene.String()
    owner = graphene.String()
    host = graphene.String()
    title = graphene.String()
    description = graphene.String()
    url = graphene.String()
    group = graphene.String()
    reloading = graphene.Boolean()
    time_zone_info = graphene.Field(QLTimeZone)
    last_updated = graphene.Float()
    status = graphene.String()
    state_totals = graphene.Field(QLStateTotals)
    states = graphene.List(graphene.String)
    run_mode = graphene.String()
    namespace_definition_order = graphene.List(graphene.String)
    newest_runahead_cycle_point = graphene.String()
    newest_cycle_point = graphene.String()
    oldest_cycle_point = graphene.String()
    tree_depth = graphene.Int()


class QLPrereq(graphene.ObjectType):
    """Task prerequisite."""
    condition = graphene.String()
    message = graphene.String()

class QLJobHost(graphene.ObjectType):
    """Task job host."""
    submit_num = graphene.Int()
    job_host = graphene.String()

class QLOutputs(graphene.ObjectType):
    """Task State Outputs"""
    expired = graphene.Boolean()
    submitted = graphene.Boolean()
    submit_failed = graphene.Boolean()
    started = graphene.Boolean()
    succeeded = graphene.Boolean()
    failed = graphene.Boolean()


class QLTask(graphene.ObjectType):
    """Task unitary."""
    class Meta:
        interfaces = (relay.Node,)

    name = graphene.String()
    label = graphene.String()
    state = graphene.String()
    title = graphene.String()
    description = graphene.String()
    URL = graphene.String()
    spawned = graphene.Boolean()
    execution_time_limit = graphene.Float()
    submitted_time = graphene.Float()
    started_time = graphene.Float()
    finished_time = graphene.Float()
    mean_elapsed_time = graphene.Float()
    submitted_time_string = graphene.String()
    started_time_string = graphene.String()
    finished_time_string = graphene.String()
    host = graphene.String()
    batch_sys_name = graphene.String()
    submit_method_id = graphene.String()
    submit_num = graphene.Int()
    namespace = graphene.List(graphene.String)
    logfiles = graphene.List(graphene.String)
    latest_message = graphene.String()
    job_hosts = graphene.List(QLJobHost)
    prerequisites = graphene.List(QLPrereq)
    outputs = graphene.Field(QLOutputs)
    parents = relay.ConnectionField(
        lambda: FamilyConnection,
        description="""Task parents.""",
        id=graphene.ID(default_value=None),
        exid=graphene.ID(default_value=None),
        items=graphene.List(graphene.ID, default_value=[]),
        exitems=graphene.List(graphene.ID, default_value=[]),
        states=graphene.List(graphene.String, default_value=[]),
        exstates=graphene.List(graphene.String, default_value=[]),
        mindepth=graphene.Int(default_value=-1),
        maxdepth=graphene.Int(default_value=-1),
        )
    node_depth = graphene.Int()

    def resolve_parents(self, info, **args):
        if self.parents:
            schd = info.context.get('schd_obj')
            args['items'] = self.parents
            return schd.info_get_graphql_nodes(args, node_type='family')
        return []

    @classmethod
    def get_node(cls, info, id):
        schd = info.context.get('schd_obj')
        return schd.info_get_graphql_task(id)


class TaskConnection(relay.Connection):
    class Meta:
        node = QLTask


class QLFamily(graphene.ObjectType):
    """Family composite."""
    class Meta:
        interfaces = (relay.Node,)

    name = graphene.String()
    label = graphene.String()
    state = graphene.String()
    title = graphene.String()
    description = graphene.String()
    URL = graphene.String()
    parents = relay.ConnectionField(
        lambda: FamilyConnection,
        description="""Family parents.""",
        id=graphene.ID(default_value=None),
        exid=graphene.ID(default_value=None),
        items=graphene.List(graphene.ID, default_value=[]),
        exitems=graphene.List(graphene.ID, default_value=[]),
        states=graphene.List(graphene.String, default_value=[]),
        exstates=graphene.List(graphene.String, default_value=[]),
        depth=graphene.Int(default_value=-1),
        mindepth=graphene.Int(default_value=-1),
        maxdepth=graphene.Int(default_value=-1),
        )
    tasks = relay.ConnectionField(
        TaskConnection,
        description="""Desendedant tasks.""",
        id=graphene.ID(default_value=None),
        exid=graphene.ID(default_value=None),
        items=graphene.List(graphene.ID, default_value=[]),
        exitems=graphene.List(graphene.ID, default_value=[]),
        states=graphene.List(graphene.String, default_value=[]),
        exstates=graphene.List(graphene.String, default_value=[]),
        mindepth=graphene.Int(default_value=-1),
        maxdepth=graphene.Int(default_value=-1),
        )
    families = relay.ConnectionField(
        lambda: FamilyConnection,
        description="""Desendedant families.""",
        id=graphene.ID(default_value=None),
        exid=graphene.ID(default_value=None),
        items=graphene.List(graphene.ID, default_value=[]),
        exitems=graphene.List(graphene.ID, default_value=[]),
        states=graphene.List(graphene.String, default_value=[]),
        exstates=graphene.List(graphene.String, default_value=[]),
        mindepth=graphene.Int(default_value=-1),
        maxdepth=graphene.Int(default_value=-1),
        )
    node_depth = graphene.Int()

    def resolve_tasks(self, info, **args):
        if self.tasks:
            schd = info.context.get('schd_obj')
            args['items'] = self.tasks
            return schd.info_get_graphql_nodes(args, node_type='task')
        return []

    def resolve_parents(self, info, **args):
        if self.parents:
            schd = info.context.get('schd_obj')
            args['items'] = self.parents
            return schd.info_get_graphql_nodes(args, node_type='family')
        return []

    def resolve_families(self, info, **args):
        if self.families:
            schd = info.context.get('schd_obj')
            args['items'] = self.families
            return schd.info_get_graphql_nodes(args, node_type='family')
        return []

    @classmethod
    def get_node(cls, info, id):
        schd = info.context.get('schd_obj')
        return schd.info_get_graphql_family(id)


class FamilyConnection(relay.Connection):
    class Meta:
        node = QLFamily


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    apiversion = graphene.Field(ApiVersion)
    globalInfo = graphene.Field(QLGlobal)
    tasks = relay.ConnectionField(
        TaskConnection,
        id=graphene.ID(default_value=None),
        exid=graphene.ID(default_value=None),
        items=graphene.List(graphene.ID, default_value=[]),
        exitems=graphene.List(graphene.ID, default_value=[]),
        states=graphene.List(graphene.String, default_value=[]),
        exstates=graphene.List(graphene.String, default_value=[]),
        mindepth=graphene.Int(default_value=-1),
        maxdepth=graphene.Int(default_value=-1),
        )

    families = relay.ConnectionField(
        FamilyConnection,
        id=graphene.ID(default_value=None),
        exid=graphene.ID(default_value=None),
        items=graphene.List(graphene.ID, default_value=[]),
        exitems=graphene.List(graphene.ID, default_value=[]),
        states=graphene.List(graphene.String, default_value=[]),
        exstates=graphene.List(graphene.String, default_value=[]),
        mindepth=graphene.Int(default_value=-1),
        maxdepth=graphene.Int(default_value=-1),
        )

    def resolve_apiversion(self, info):
        version = info.context.get('app_server').config['API']
        return {'version': version}

    def resolve_globalInfo(self, info):
        schd = info.context.get('schd_obj')
        return schd.info_get_graphql_global()

    def resolve_tasks(self, info, **args):
        schd = info.context.get('schd_obj')
        return schd.info_get_graphql_nodes(args, node_type='task')

    def resolve_families(self, info, **args):
        schd = info.context.get('schd_obj')
        return schd.info_get_graphql_nodes(args, node_type='family')


schema = graphene.Schema(query=Query)