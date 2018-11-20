#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA & British Crown (Met Office) & Contributors.
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
"""HTTP(S) server, and suite runtime API service facade exposed.

Implementation currently using flask via gevent.
"""

from gevent import pywsgi

import ast
import binascii
import os
import socket
import ssl
import random
import re
import inspect
from hashlib import md5, sha1
from time import time
from uuid import uuid4
from functools import wraps

import flask
from flask_graphql import GraphQLView
from cylc.network.schema import schema

from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
import cylc.flags
from cylc.network import (
    NO_PASSPHRASE, PRIVILEGE_LEVELS, PRIV_IDENTITY, PRIV_DESCRIPTION,
    PRIV_STATE_TOTALS, PRIV_FULL_READ, PRIV_SHUTDOWN, PRIV_FULL_CONTROL)
from cylc.hostuserutil import get_host
from cylc import LOG
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.unicode_util import utf8_enforce
from cylc.version import CYLC_VERSION
from cylc.wallclock import RE_DATE_TIME_FORMAT_EXTENDED

auth_scheme = glbl_cfg().get(['communication', 'authentication scheme'])
comms_options = glbl_cfg().get(['communication', 'options'])
srv_files_mgr = SuiteSrvFilesManager()

if auth_scheme == 'basic':
    from flask_httpauth import HTTPBasicAuth
    auth = HTTPBasicAuth()
elif auth_scheme == 'digest':
    from flask_httpauth import HTTPDigestAuth
    auth = HTTPDigestAuth(use_ha1_pw=True)
    auth.user_digest = {}

user_priv = { 
        'cylc': PRIVILEGE_LEVELS[-1],
    }
        #'anon': PRIV_STATE_TOTALS,

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
 
    def to_dict(self):
        rv = dict(self.payload or ()) 
        rv['message'] = self.message
        return rv


# Client sessions, 'time' is time of latest visit.
# Some methods may store extra info to the client session dict.
# {UUID: {'time': TIME, ...}, ...}
clients = {}
# Start of id requests measurement
_id_start_time = time()
# Number of client id requests
_num_id_requests = 0

CLIENT_FORGET_SEC = 60
CLIENT_ID_MIN_REPORT_RATE = 1.0  # 1 Hz
CLIENT_ID_REPORT_SECONDS = 3600  # Report every 1 hour.
CONNECT_DENIED_PRIV_TMPL = ( 
    "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s %s" )
LOG_COMMAND_TMPL = '[client-command] %s %s@%s:%s %s'
LOG_IDENTIFY_TMPL = '[client-identify] %d id requests in PT%dS'
LOG_FORGET_TMPL = '[client-forget] %s'
LOG_CONNECT_ALLOWED_TMPL = "[client-connect] %s@%s:%s privilege='%s' %s"
LOG_CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"
    
#** Client info and privilege checking
def _get_client_info():
    """Return information about the most recent flask request, if any."""
    try:
        auth_user = flask.request.authorization.username
    except AttributeError:
        auth_user = None
    info = flask.request.headers
    origin_string = info.get("User-Agent", "")
    origin_props = {}
    if origin_string:
        try:
            origin_props = dict(
                [_.split("/", 1) for _ in origin_string.split()]
            )
        except ValueError:
            pass
    prog_name = origin_props.get("prog_name", "Unknown")
    uuid = origin_props.get("uuid", uuid4())
    if info.get("From") and "@" in info["From"]:
        user, host = info["From"].split("@")
    else:
        user, host = ("Unknown", "Unknown")
    return auth_user, prog_name, user, host, uuid


#** API object creation
def create_app(schd_obj):
    """HTTP(S) server by flask-gevent, for serving suite runtime API."""
    app = flask.Flask(__name__)
    
    # Make scheduler object available via the config
    app.config.update(
        DEBUG = False,
        SECRET_KEY = binascii.hexlify(os.urandom(16)),
        JSONIFY_PRETTYPRINT_REGULAR = False,
        COMMS_METHOD = glbl_cfg().get(['communication', 'method']),
        AUTH_SCHEME = glbl_cfg().get(
            ['communication', 'authentication scheme']),
        CYLC_SCHEDULER = schd_obj,
        API = 3
        )

    users = {
        'cylc': srv_files_mgr.get_auth_item(srv_files_mgr.FILE_BASE_PASSPHRASE,
            schd_obj.suite, content=True),
        'anon': NO_PASSPHRASE
         }

    if auth_scheme == 'basic':
        for username in users:
            if "SHA1" in comms_options: 
                # Note 'SHA1' not 'SHA'.
                users[username] = sha1(users.get(username)).hexdigest()
            else:
                users[username] = md5(users.get(username)).hexdigest()

        @auth.get_password
        def get_pw(username):
            if username in users:
                return users.get(username)
            return None

        @auth.hash_password
        def hash_pw(password):
            if "SHA1" in comms_options:
                return sha1(password).hexdigest()
            else:
                return md5(password).hexdigest()

    elif auth_scheme == 'digest':
        @auth.get_password
        def get_pw(username):
            if username in users:
                return auth.generate_ha1(username,users.get(username))
            return None
        
        def _generate_digest_pair():
            return {
                'nonce': md5(str(random.SystemRandom().random()
                    ).encode('utf-8')).hexdigest(),
                'opaque': md5(str(random.SystemRandom().random()
                    ).encode('utf-8')).hexdigest()}

        @auth.generate_nonce
        def generate_nonce():
            """Return the nonce value to use for this client."""
            auth_user = flask.request.headers.get("From")
            try:
                return auth.user_digest[auth_user]['nonce']
            except KeyError:
                auth.user_digest[auth_user] = _generate_digest_pair() 
            return auth.user_digest[auth_user]['nonce']
        
        @auth.verify_nonce
        def verify_nonce(nonce):
            """Verify that the nonce value sent by the client is correct."""
            auth_user = flask.request.headers.get("From")
            return nonce == auth.user_digest[auth_user]['nonce']
        
        @auth.generate_opaque
        def generate_opaque():
            """Return the opaque value to use for this client."""
            auth_user = flask.request.headers.get("From")
            try:
                return auth.user_digest[auth_user]['opaque']
            except KeyError:
                auth.user_digest[auth_user] = _generate_digest_pair() 
            return auth.user_digest[auth_user]['opaque']
            
        @auth.verify_opaque
        def verify_opaque(opaque):
            """Verify that the opaque value sent by the client is correct."""
            auth_user = flask.request.headers.get("From")
            return opaque == auth.user_digest[auth_user]['opaque']


    @app.errorhandler(InvalidUsage)
    def handle_invalid_usage(error):
        response = flask.jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    api = api_blueprint(app)
    app.register_blueprint(api)
    app.register_blueprint(api, url_prefix='/id')

    def graphql_view():
        view = GraphQLView.as_view(
            'graphql',
            schema=schema,
            graphiql=True,
            get_context=lambda: {
                'schd_obj': schd_obj,
                'app_server': app,
                'request': flask.request
                }
        )
        return auth.login_required(view)
 
    app.add_url_rule(
        '/graphql',
        view_func=graphql_view(),
        methods = ['GET', 'POST']
    )

    @app.after_request
    def after_request(response):
        if "Authorization" not in flask.request.headers:
            # Probably just the initial HTTPS handshake.
            connection_denied = False
        elif isinstance(response.status, basestring):
            connection_denied = response.status.split()[0] in ["401", "403"]
        else:
            connection_denied = response.status in [401, 403]
        if connection_denied:
            prog_name, user, host, uuid = _get_client_info()[1:]
            LOG.warning(LOG_CONNECT_DENIED_TMPL, user, host, prog_name, uuid)
        return response
    return app


def start_app(app):
    """Determine server HTTP security, port, host, and initiate app service"""
    suite = app.config['CYLC_SCHEDULER'].suite
    # set host
    host = get_host()
    flask_options = {'host': host}

    # set COMMS method
    comms_method = app.config['COMMS_METHOD']
    if comms_method == 'http':
        context = None
    else:
        try:
            context = (srv_files_mgr.get_auth_item(
                    srv_files_mgr.FILE_BASE_SSL_CERT, suite), 
                    srv_files_mgr.get_auth_item(
                    srv_files_mgr.FILE_BASE_SSL_PEM, suite))
            flask_options['ssl_context'] = context
        except SuiteServiceFileError:
            LOG.error("no HTTPS/OpenSSL support. Aborting...")
            raise CylcError("No HTTPS support. "
                            "Configure user's global.rc to use HTTP.")
    
    # Figure out the ports we are allowed to use.
    ok_ports = glbl_cfg().get(['suite servers', 'run ports'])
    random.shuffle(ok_ports)

    # Check on specified host for free port
    for port in ok_ports:
        sock_check = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock_check.settimeout(1)
            sock_check.connect((host,port))
            sock_check.close()
        except socket.error:
            # host:port not in use
            flask_options['port'] = port
            try:
                #app.run(**flask_options)
                if comms_method == 'http':
                    app_server = pywsgi.WSGIServer((host, port), app)
                    srv_start_msg = "Server started:  http://%s:%s"
                else:
                    app_server = pywsgi.WSGIServer((host, port), app, log=None,
                        certfile=context[0], keyfile=context[1])

                app_server.start()
                return app_server
            except:
                print "Unable to start api on port", port
            
        if port == ok_ports[-1]:
            raise Exception("No available ports")

def shutdown(app_server):
    """Shutdown the web server."""
    if hasattr(app_server, "stop"):
        app_server.stop()

def get_port(app_server):
    """Return the web server port."""
    if hasattr(app_server, "server_port"):
        return app_server.server_port

def api_blueprint(app):

    api_blu = flask.Blueprint('api', __name__)

    schd = app.config['CYLC_SCHEDULER']
    suite = schd.suite

    RE_MESSAGE_TIME = re.compile(
        r'\A(.+) at (' + RE_DATE_TIME_FORMAT_EXTENDED + r')\Z', re.DOTALL)

    # Privilege checking decorator
    def priv_check(privilege, log_info=True):
        def priv_decorator(func):
            @wraps(func)
            def priv_wrapper(*args, **kwargs):
                command = func.__name__
                _check_access_priv_and_report(privilege, command, log_info)
                return func(*args, **kwargs)
            return priv_wrapper
        return priv_decorator
    

    #** EndPoints **
    @api_blu.route('/apiversion', methods = ['GET', 'POST'])
    def apiversion():
        """Return API version."""
        return str(app.config['API'])

    @api_blu.route('/clear_broadcast', methods = ['POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def clear_broadcast():
        """Clear settings globally, or for listed namespaces and/or points.

        Return a tuple (modified_settings, bad_options), where:
        * modified_settings is similar to the return value of the "put" method,
          but for removed settings.
        * bad_options is a dict in the form:
              {"point_strings": ["20020202", ..."], ...}
          The dict is only populated if there are options not associated with
          previous broadcasts. The keys can be:
          * point_strings: a list of bad point strings.
          * namespaces: a list of bad namespaces.
          * cancel: a list of tuples. Each tuple contains the keys of a bad
            setting.
          JSON data e.g:
          '{"point_strings": ["*"], "namespaces": ["foo"], 
          "cancel_settings": [{"environment": {"PERSON": "Bob"}}]}'
        """
        if not flask.request.is_json:
            err = "Unsupported Content-Type: must be application/json"
            raise InvalidUsage(err, status_code=415)
        req_data = flask.request.get_json()
        point_strings = utf8_enforce(req_data.get('point_strings'))
        namespaces = utf8_enforce(req_data.get('namespaces'))
        cancel_settings = utf8_enforce(req_data.get('cancel_settings'))
        return flask.jsonify(
            schd.task_events_mgr.broadcast_mgr.clear_broadcast(
            point_strings, namespaces, cancel_settings))

    @api_blu.route('/dry_run_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def dry_run_tasks():
        """Prepare job file for a task.

        items[0] is an identifier for matching a task proxy.
        """
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        check_syntax = _literal_eval('check_syntax', 
            flask.request.args.get('check_syntax'))
        if check_syntax is None:
            check_syntax = True
        schd.command_queue.put(('dry_run_tasks', (items,),
                               {'check_syntax': check_syntax}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/expire_broadcast', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def expire_broadcast():
        """Clear all settings targeting cycle points earlier than cutoff."""
        cutoff = flask.request.args.get('cutoff')
        return flask.jsonify(
            schd.task_events_mgr.broadcast_mgr.expire_broadcast(cutoff))

    @api_blu.route('/get_broadcast', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_broadcast():
        """Retrieve all broadcast variables that target a given task ID."""
        task_id = flask.request.args.get('task_id')
        return flask.jsonify(
            schd.task_events_mgr.broadcast_mgr.get_broadcast(task_id))

    @api_blu.route('/get_cylc_version', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_IDENTITY)
    def get_cylc_version():
        """Return the cylc version running this suite."""
        return flask.jsonify(CYLC_VERSION)

    @api_blu.route('/get_graph_raw', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_graph_raw():
        """Return raw suite graph."""
        req_data = flask.request.args
        start_point_string = req_data.get('start_point_string')
        group_nodes = _literal_eval('group_nodes',
            req_data.get('group_nodes'), [req_data.get('group_nodes')])
        ungroup_nodes = _literal_eval('ungroup_nodes',
            req_data.get('ungroup_nodes'), [req_data.get('ungroup_nodes')])
        ungroup_recursive = _literal_eval('ungroup_recursive',
            req_data.get('ungroup_recursive'))
        if ungroup_recursive is None:
            ungroup_recursive = False
        group_all = _literal_eval('group_all', req_data.get('group_all'))
        if group_all is None:
            group_all = False
        ungroup_all = _literal_eval('ungroup_all', req_data.get('ungroup_all'))
        if ungroup_all is None:
            ungroup_all= False
        # Ensure that a "None" str is converted to the None value.
        stop_point_string = _literal_eval('stop_point_string',
            req_data.get('stop_point_string'),req_data.get('stop_point_string'))
        if stop_point_string is not None:
            stop_point_string = str(stop_point_string)
        return flask.jsonify(schd.info_get_graph_raw(start_point_string,
            stop_point_string, group_nodes=group_nodes,
            ungroup_nodes=ungroup_nodes, ungroup_recursive=ungroup_recursive,
            group_all=group_all, ungroup_all=ungroup_all))

    @api_blu.route('/get_latest_state', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_latest_state():
        """Return latest suite state (suitable for a GUI update)."""
        client_info = _check_access_priv_and_report(PRIV_FULL_READ)
        full_mode = _literal_eval('full_mode',
            flask.request.args.get('full_mode'))
        if full_mode is None:
            full_mode = False
        return flask.jsonify(
            schd.info_get_latest_state(client_info, full_mode))

    @api_blu.route('/get_suite_info', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_DESCRIPTION)
    def get_suite_info():
        """Return a dict containing the suite title and description."""
        return flask.jsonify(schd.info_get_suite_info())

    @api_blu.route('/get_suite_state_summary', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_suite_state_summary():
        """Return the global, task, and family summary data structures."""
        return flask.jsonify(schd.info_get_suite_state_summary())

    @api_blu.route('/get_task_info', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_task_info():
        """Return info of a task."""
        names = flask.request.args.get('names')
        if not isinstance(names, list):
            names = [names]
        return flask.jsonify(schd.info_get_task_info(names))

    @api_blu.route('/get_task_jobfile_path', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_task_jobfile_path():
        """Return task job file path."""
        task_id = flask.request.args.get('task_id')
        return flask.jsonify(schd.info_get_task_jobfile_path(task_id))

    @api_blu.route('/get_task_requisites', methods = ['GET'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def get_task_requisites():
        """Return prerequisites of a task."""
        list_prereqs = flask.request.args.get('list_prereqs')
        if list_prereqs is None:
            list_prereqs = False
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        return flask.jsonify(schd.info_get_task_requisites(
            items, list_prereqs=(list_prereqs in [True, 'True'])))

    @api_blu.route('/hold_after_point_string', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def hold_after_point_string():
        """Set hold point of suite."""
        point_string = flask.request.args.get('point_string')
        schd.command_queue.put(
            ("hold_after_point_string", (point_string,), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/hold_suite', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def hold_suite():
        """Hold the suite."""
        schd.command_queue.put(("hold_suite", (), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/hold_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def hold_tasks():
        """Hold tasks.

        items is a list of identifiers for matching task proxies.
        """
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        schd.command_queue.put(("hold_tasks", (items,), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/identify', methods = ['GET'])
    @auth.login_required
    def identify():
        """Return suite identity, (description, (states))."""
        _report_id_requests()
        privileges = []
        for privilege in PRIVILEGE_LEVELS[0:3]:
            if _access_priv_ok(privilege):
                privileges.append(privilege)
        return flask.jsonify(schd.info_get_identity(privileges))

    @api_blu.route('/insert_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def insert_tasks():
        """Insert task proxies.

        items is a list of identifiers of (families of) task instances.
        """
        req_data = flask.request.args
        items = req_data.get('items')
        stop_point_string = req_data.get('stop_point_string')
        no_check = req_data.get('no_check')
        if not isinstance(items, list):
            items = [items]
        if stop_point_string == "None":
            stop_point_string = None
        schd.command_queue.put((
            "insert_tasks",
            (items,),
            {"stop_point_string": stop_point_string,
             "no_check": no_check in ['True', True]}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/kill_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def kill_tasks():
        """Kill task jobs.

        items is a list of identifiers for matching task proxies.
        """
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        schd.command_queue.put(("kill_tasks", (items,), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/nudge', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def nudge():
        """Tell suite to try task processing."""
        schd.command_queue.put(("nudge", (), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/ping_suite', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_IDENTITY)
    def ping_suite():
        """Return True."""
        return flask.jsonify(True)

    @api_blu.route('/ping_task', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_READ)
    def ping_task():
        """Return True if task_id exists (and running)."""
        req_data = flask.request.args
        task_id = req_data.get('task_id')
        exists_only = _literal_eval('exists_only', req_data.get('exists_only'))
        if exists_only is None:
            exists_only = False
        return flask.jsonify(
            schd.info_ping_task(task_id, exists_only=exists_only))

    @api_blu.route('/poll_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def poll_tasks():
        """Poll task jobs.

        items is a list of identifiers for matching task proxies.
        """
        req_data = flask.request.args
        items = req_data.get('items')
        poll_succ = req_data.get('poll_succ')
        if poll_succ is None:
            poll_succ = False
        if items is not None and not isinstance(items, list):
            items = [items]
        schd.command_queue.put(
            ("poll_tasks", (items,),
                {"poll_succ": poll_succ in ['True', True]}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/put_broadcast', methods = ['POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def put_broadcast():
        """Add new broadcast settings (server side interface).

        Return a tuple (modified_settings, bad_options) where:
          modified_settings is list of modified settings in the form:
            [("20200202", "foo", {"command scripting": "true"}, ...]
          bad_options is as described in the docstring for clear().
        JSON data form:
        '{"point_strings": ["*"], "namespaces": ["foo"],
         "settings": [{"environment": {"PERSON": "Bob"}}]}'
        """
        if not flask.request.is_json:
            err = "Unsupported Content-Type: must be application/json"
            raise InvalidUsage(err, status_code=415)
        req_data = flask.request.get_json()
        point_strings = utf8_enforce(req_data.get('point_strings'))
        namespaces = utf8_enforce(req_data.get('namespaces'))
        settings = utf8_enforce(req_data.get('settings'))
        return flask.jsonify(schd.task_events_mgr.broadcast_mgr.put_broadcast(
            point_strings, namespaces, settings))

    @api_blu.route('/put_ext_trigger', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def put_ext_trigger():
        """Server-side external event trigger interface."""
        event_message = flask.request.args.get('event_message')
        event_id = flask.request.args.get('event_id')
        schd.ext_trigger_queue.put((event_message, event_id))
        return flask.jsonify(True, 'Event queued')

    @api_blu.route('/put_message', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL, log_info=False)
    def put_message():
        """(Compat) Put task message.

        Arguments:
            task_id (str): Task ID in the form "TASK_NAME.CYCLE".
            severity (str): Severity level of message.
            message (str): Content of message.
        """
        req_data = flask.request.args
        task_id = req_data.get('task_id')
        severity = req_data.get('severity')
        message = req_data.get('message')
        match = RE_MESSAGE_TIME.match(message)
        event_time = None
        if match:
            message, event_time = match.groups()
        schd.message_queue.put((task_id, event_time, severity, message))
        return flask.jsonify(True, 'Message queued')

    @api_blu.route('/put_messages', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL, log_info=False)
    def put_messages():
        """Put task messages in queue for processing later by the main loop.

        Arguments:
            task_job (str): Task job in the form "CYCLE/TASK_NAME/SUBMIT_NUM".
            event_time (str): Event time as string.
            messages (list): List in the form [[severity, message], ...].
        """
        if not flask.request.is_json:
            err = "Unsupported Content-Type: must be application/json"
            raise InvalidUsage(err, status_code=415)
        req_data = flask.request.get_json()
        task_job = utf8_enforce(req_data.get('task_job'))
        event_time = utf8_enforce(req_data.get('event_time'))
        messages = utf8_enforce(req_data.get('messages'))
        for severity, message in messages:
            schd.message_queue.put((task_job, event_time, severity, message))
        return flask.jsonify(True, 'Messages queued: %d' % len(messages))

    @api_blu.route('/reload_suite', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def reload_suite():
        """Tell suite to reload the suite definition."""
        schd.command_queue.put(("reload_suite", (), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/release_suite', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def release_suite():
        """Unhold suite."""
        schd.command_queue.put(("release_suite", (), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/release_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def release_tasks():
        """Unhold tasks.

        items is a list of identifiers for matching task proxies.
        """
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        schd.command_queue.put(("release_tasks", (items,), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/remove_cycle', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def remove_cycle():
        """Remove tasks in a cycle from task pool."""
        point_string = flask.request.args.get('point_string')
        spawn = _literal_eval('spawn', flask.request.args.get('spawn'))
        schd.command_queue.put(
            ("remove_tasks", ('%s/*' % point_string,), {"spawn": spawn}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/remove_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def remove_tasks():
        """Remove tasks from task pool.

        items is a list of identifiers for matching task proxies.
        """
        items = flask.request.args.get('items')
        spawn = _literal_eval('spawn', flask.request.args.get('spawn'))
        if not isinstance(items, list):
            items = [items]
        schd.command_queue.put(
            ("remove_tasks", (items,), {"spawn": spawn}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/reset_task_states', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def reset_task_states():
        """Reset statuses tasks.

        items is a list of identifiers for matching task proxies.
        """
        req_data = flask.request.args
        items = req_data.get('items')
        state = req_data.get('state')
        outputs = req_data.get('outputs')
        if not isinstance(items, list):
            items = [items]
        if outputs and not isinstance(outputs, list):
            outputs = [outputs]
        schd.command_queue.put(
            ("reset_task_states",
                 (items,), {"state": state, "outputs": outputs}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/set_stop_after_clock_time', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_SHUTDOWN)
    def set_stop_after_clock_time():
        """Set suite to stop after wallclock time."""
        schd.command_queue.put(("set_stop_after_clock_time",
            (flask.request.args.get('datetime_string'),), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/set_stop_after_point', methods = ['POST'])
    @auth.login_required
    @priv_check(PRIV_SHUTDOWN)
    def set_stop_after_point():
        """Set suite to stop after cycle point."""
        schd.command_queue.put(("set_stop_after_point",
            (flask.request.args.get('point_string'),), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/set_stop_after_task', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_SHUTDOWN)
    def set_stop_after_task():
        """Set suite to stop after an instance of a task."""
        schd.command_queue.put(("set_stop_after_task",
            (flask.request.args.get('task_id'),), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/set_stop_cleanly', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_SHUTDOWN)
    def set_stop_cleanly():
        """Set suite to stop cleanly or after kill active tasks."""
        kill_active_tasks = _literal_eval('kill_active_tasks',
            flask.request.args.get('kill_active_tasks'))
        if kill_active_tasks is None:
            kill_active_tasks = False
        schd.command_queue.put(
            ("set_stop_cleanly", (), {"kill_active_tasks": kill_active_tasks}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/set_verbosity', methods = ['GET','POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def set_verbosity():
        """Set suite verbosity to new level."""
        schd.command_queue.put(("set_verbosity",
            (flask.request.args.get('level'),), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/signout', methods = ['GET', 'POST'])
    @auth.login_required
    def signout():
        """Forget client, where possible."""
        uuid = _get_client_info()[4]
        try:
            del clients[uuid]
        except KeyError:
            return flask.jsonify(False)
        else:
            LOG.debug(LOG_FORGET_TMPL, uuid)
            return flask.jsonify(True)

    @api_blu.route('/spawn_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def spawn_tasks():
        """Spawn tasks.

        items is a list of identifiers for matching task proxies.
        """
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        schd.command_queue.put(("spawn_tasks", (items,), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/stop_now', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_SHUTDOWN)
    def stop_now():
        """Stop suite on event handler completion, or terminate right away."""
        terminate = _literal_eval('terminate',
            flask.request.args.get('terminate'))
        if terminate is None:
            terminate = False
        schd.command_queue.put(("stop_now", (), {"terminate": terminate}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/take_checkpoints', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def take_checkpoints():
        """Checkpoint current task pool.

        items[0] is the name of the checkpoint.
        """
        items = flask.request.args.get('items')
        if not isinstance(items, list):
            items = [items]
        schd.command_queue.put(("take_checkpoints", (items,), {}))
        return flask.jsonify(True, 'Command queued')

    @api_blu.route('/trigger_tasks', methods = ['GET', 'POST'])
    @auth.login_required
    @priv_check(PRIV_FULL_CONTROL)
    def trigger_tasks():
        """Trigger submission of task jobs where possible.

        items is a list of identifiers for matching task proxies.
        """
        items = flask.request.args.get('items')
        back_out = _literal_eval('back_out', 
            flask.request.args.get('back_out'))
        if back_out is None:
            back_out = False
        if not isinstance(items, list):
            items = [items]
        items = [str(item) for item in items]
        schd.command_queue.put(
            ("trigger_tasks", (items,), {"back_out": back_out}))
        return flask.jsonify(True, 'Command queued')


    #** Priviledge checking
    def _access_priv_ok(required_privilege_level):
        """Return True if a client has enough privilege for given level.
    
        The required privilege level is compared to the level granted to the
        client by the connection validator (held in thread local storage).
    
        """
        try:
            return _check_access_priv(required_privilege_level)
        except InvalidUsage:
            return False
    
    def _check_access_priv(required_privilege_level):
        """Raise an exception if client privilege is insufficient.
    
        (See the documentation above for the boolean version of this function).
    
        """
        auth_user, prog_name, user, host, uuid = _get_client_info()
        priv_level = _get_priv_level(auth_user)
        if (PRIVILEGE_LEVELS.index(priv_level) <
                PRIVILEGE_LEVELS.index(required_privilege_level)):
            err = CONNECT_DENIED_PRIV_TMPL % (
                priv_level, required_privilege_level,
                user, host, prog_name, uuid)
            LOG.warning(CONNECT_DENIED_PRIV_TMPL, 
                priv_level, required_privilege_level,
                user, host, prog_name, uuid)
            # Raise an exception to be sent back to the client.
            raise InvalidUsage(err, status_code=403)
        return True
    
    def _check_access_priv_and_report(required_privilege_level, command=None,
        log_info=True):
        """Check access privilege and log requests with identifying info.
    
        In debug mode log all requests including task messages. Otherwise log
        all user commands, and just the first info command from each client.
    
        Return:
            dict: containing the client session
    
        """
        _check_access_priv(required_privilege_level)
        if command is None:
            command = inspect.currentframe().f_back.f_code.co_name
        auth_user, prog_name, user, host, uuid = _get_client_info()
        priv_level = _get_priv_level(auth_user)
        LOG.debug(LOG_CONNECT_ALLOWED_TMPL,
            user, host, prog_name, priv_level, uuid)
        if cylc.flags.debug or uuid not in clients and log_info:
            LOG.info(LOG_COMMAND_TMPL, command, user, host, prog_name, uuid)
        clients.setdefault(uuid, {})
        clients[uuid]['time'] = time()
        _housekeep()
        return clients[uuid]
    
    def _report_id_requests():
        """Report the frequency of identification (scan) requests."""
        global _num_id_requests
        global _id_start_time
        _num_id_requests += 1
        now = time()
        interval = now - _id_start_time
        if interval > CLIENT_ID_REPORT_SECONDS:
            rate = float(_num_id_requests) / interval
            if rate > self.CLIENT_ID_MIN_REPORT_RATE:
                LOG.warning(LOG_IDENTIFY_TMPL, _num_id_requests, interval)
            else:
                LOG.debug(LOG_IDENTIFY_TMPL, _num_id_requests, interval)
            _id_start_time = now
            _num_id_requests = 0
        uuid = _get_client_info()[4]
        clients.setdefault(uuid, {})
        clients[uuid]['time'] = now
        _housekeep()
       
    def _get_priv_level(auth_user):
        """Get the privilege level for this authenticated user."""
        if auth_user in user_priv:
            return user_priv.get(auth_user)
        elif schd.config.cfg['cylc']['authentication']['public']:
            return schd.config.cfg['cylc']['authentication']['public']
        else:
            return glbl_cfg().get(['authentication', 'public'])

    def _forget_client(uuid):
        """Forget a client."""
        try:
            client_info = clients.pop(uuid)
        except KeyError:
            return False
        if client_info.get('err_log_handler') is not None:
            LOG.removeHandler(client_info.get('err_log_handler'))
        LOG.debug(LOG_FORGET_TMPL, uuid)
        return True
    
    def _housekeep():
        """Forget inactive clients."""
        for uuid, client_info in clients.copy().items():
            if time() - client_info['time'] > CLIENT_FORGET_SEC:
                _forget_client(uuid)
    
    # Sting to python value
    def _literal_eval(key, value, default=None):
        """Wrap ast.literal_eval if value is basestring.
    
        On SyntaxError or ValueError, return default is default is not None.
        Otherwise, raise HTTPError 400.
        """
        if isinstance(value, basestring):
            try:
                return ast.literal_eval(value)
            except (SyntaxError, ValueError):
                if default is not None:
                    return default
                raise InvalidUsage(
                    r'Bad argument value: %s=%s' % (key, value),400)
        else:
            return value


    return api_blu


