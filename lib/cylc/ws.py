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

"""Web service CLI and mod_wsgi functions.

wsgi_app - Return a WSGI application for a web service.
ws_cli - Parse CLI. Start/Stop ad-hoc server.

"""

import cherrypy
from glob import glob
import os
import signal

from cylc.option_parsers import CylcOptionParser as COP

LOG_ROOT_TMPL = "~/.cylc/%(ns)s-%(util)s-%(host)s-%(port)s"


def wsgi_app(service_cls, *args, **kwargs):
    """Return a WSGI application.

    service_cls - Class to launch web service. Must have the constants
                  service_cls.NS and service_cls.UTIL. *args and **kwargs are
                  passed to its constructor.
    """
    cherrypy.server.unsubscribe()
    cherrypy.config.update({'engine.autoreload.on': False})
    cherrypy.config.update({'environment': 'embedded'})
    cherrypy.engine.start()
    cherrypy.engine.signal_handler.unsubscribe()
    config = _configure(service_cls)
    try:
        return cherrypy.Application(service_cls(*args, **kwargs), None, config)
    finally:
        cherrypy.engine.stop()


def ws_cli(service_cls, *args, **kwargs):
    """Parse command line, start/stop ad-hoc server.

    service_cls - Class to launch web service. Must have the constants
                  service_cls.NS and service_cls.UTIL. *args and **kwargs are
                  passed to its constructor.
    """
    parser = COP(__doc__, jset=True, prep=True, icp=True)

    parser.add_option(
        "--non-interactive", "--yes", "-y",
        help="Switch off interactive prompting.",
        action="store_true", default=False, dest="non_interactive")
    parser.add_option(
        "--service-root", "-R",
        help="Include web service name under root of URL.",
        action="store_true", default=False, dest="service_root_mode")

    opts, args = parser.parse_args()
    arg = None
    if args:
        arg = args[0]
    if arg == "start":
        port = None
        if args[1:]:
            port = args[1]
        _ws_init(service_cls, port, opts.service_root_mode, *args, **kwargs)
    else:
        status = _get_server_status(service_cls)
        for key, value in sorted(status.items()):
            print "%s=%s\n" % (key, value)
        if (arg == "stop" and status.get("pid") and
                (opts.non_interactive or
                 raw_input("Stop server? y/n (default=n)") == "y")):
            os.killpg(int(status["pid"]), signal.SIGTERM)
            # TODO: should check whether it is killed or not


def _ws_init(service_cls, port, service_root_mode, *args, **kwargs):
    """Start quick web service."""
    config = _configure(service_cls)

    cherrypy.config["server.socket_host"] = "0.0.0.0"
    if port:
        cherrypy.config["server.socket_port"] = int(port)
    port = cherrypy.server.socket_port
    log_root = os.path.expanduser(LOG_ROOT_TMPL % {
        "ns": service_cls.NS,
        "util": service_cls.UTIL,
        "host": cherrypy.server.socket_host,
        "port": cherrypy.server.socket_port})
    log_status = log_root + ".status"
    if not os.path.isdir(os.path.dirname(log_root)):
        os.makedirs(os.path.dirname(log_root))
    with open(log_status, "w") as handle:
        handle.write("host=%s\n" % cherrypy.server.socket_host)
        handle.write("port=%d\n" % cherrypy.server.socket_port)
        handle.write("pid=%d\n" % os.getpid())

    cherrypy.config["log.access_file"] = log_root + "-access.log"
    open(cherrypy.config["log.access_file"], "w").close()
    cherrypy.config["log.error_file"] = log_root + "-error.log"
    open(cherrypy.config["log.error_file"], "w").close()

    root = "/"
    if service_root_mode:
        root = "/%s-%s/" % (service_cls.NS, service_cls.UTIL)
    cherrypy.tree.mount(service_cls(*args, **kwargs), root, config)
    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    finally:
        os.unlink(log_status)


def _configure(service_cls):
    """Configure cherrypy and return a dict for the specified cherrypy app."""
    # Environment variables (not normally defined in WSGI mode)
    if not os.getenv("CYLC_HOME"):
        path = os.path.abspath(__file__)
        while os.path.dirname(path) != path:  # not root
            if os.path.basename(path) == "lib":
                os.environ["CYLC_HOME"] = os.path.dirname(path)
                break
            path = os.path.dirname(path)
    for key, value in (
            ("CYLC_NS", service_cls.NS), ("CYLC_UTIL", service_cls.UTIL)):
        if os.getenv(key) is None:
            os.environ[key] = value

    # Configuration for HTML library
    cherrypy.config["tools.encode.on"] = True
    cherrypy.config["tools.encode.encoding"] = "utf-8"
    config = {}
    static_lib = get_util_home("lib", "cylc", "cylc-nameless", "static")
    for name in os.listdir(static_lib):
        path = os.path.join(static_lib, name)
        if os.path.isdir(path):
            path_key = "tools.staticdir.dir"
            bool_key = "tools.staticdir.on"
        else:
            path_key = "tools.staticfile.filename"
            bool_key = "tools.staticfile.on"
        config["/" + name] = {path_key: path, bool_key: True}
        if name == service_cls.NS + "-favicon.png":
            config["/favicon.ico"] = config["/" + name]
    return config


def _get_server_status(service_cls):
    """Return a dict containing 'cylc nameless' quick server status."""
    ret = {}
    log_root_glob = os.path.expanduser(LOG_ROOT_TMPL % {
        "ns": service_cls.NS,
        "util": service_cls.UTIL,
        "host": "*",
        "port": "*"})
    for filename in glob(log_root_glob):
        try:
            for line in open(filename):
                key, value = line.strip().split("=", 1)
                ret[key] = value
            break
        except (IOError, ValueError):
            pass
    return ret


def get_util_home(*args):
    """Return CYLC_HOME or the dirname of the dirname of sys.argv[0].

    If args are specified, they are added to the end of returned path.

    """
    try:
        value = os.environ["CYLC_HOME"]
    except KeyError:
        value = os.path.abspath(__file__)
        for _ in range(4):  # assume __file__ under $CYLC_HOME/
            value = os.path.dirname(value)
    return os.path.join(value, *args)
