#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
from pathlib import Path


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


def _ws_init(service_cls, port, service_root, *args, **kwargs):
    """Start quick web service."""
    config = _configure(service_cls)

    cherrypy.config["server.socket_host"] = "0.0.0.0"
    if port:
        cherrypy.config["server.socket_port"] = int(port)
    port = cherrypy.server.socket_port
    log_root = os.path.expanduser(
        LOG_ROOT_TMPL
        % {
            "ns": service_cls.NS,
            "util": service_cls.UTIL,
            "host": cherrypy.server.socket_host,
            "port": cherrypy.server.socket_port,
        }
    )
    log_status = log_root + ".status"
    if not os.path.isdir(os.path.dirname(log_root)):
        os.makedirs(os.path.dirname(log_root))
    Path(log_status).write_text(
        f"host={cherrypy.server.socket_host}\n"
        f"port={cherrypy.server.socket_port}\n"
        f"pid={os.getpid()}\n"
    )

    cherrypy.config["log.access_file"] = log_root + "-access.log"
    Path(cherrypy.config["log.access_file"]).touch()
    cherrypy.config["log.error_file"] = log_root + "-error.log"
    Path(cherrypy.config["log.error_file"]).touch()

    root = '/'
    if service_root != '/':
        root = "/%s-%s/" % (service_root, service_cls.UTIL)
    cherrypy.tree.mount(service_cls(*args, **kwargs), root, config)
    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    finally:
        os.unlink(log_status)


def _configure(service_cls):
    """Configure cherrypy and return a dict for the specified cherrypy app."""
    # Environment variables (not normally defined in WSGI mode)
    if not os.getenv("CYLC_DIR"):
        path = os.path.abspath(__file__)
        while os.path.dirname(path) != path:  # not root
            if os.path.basename(path) == "lib":
                os.environ["CYLC_DIR"] = os.path.dirname(path)
                break
            path = os.path.dirname(path)
    for key, value in (
        ("CYLC_NS", service_cls.NS),
        ("CYLC_UTIL", service_cls.UTIL),
    ):
        if os.getenv(key) is None:
            os.environ[key] = value

    # Configuration for HTML library
    cherrypy.config["tools.encode.on"] = True
    cherrypy.config["tools.encode.encoding"] = "utf-8"
    config = {}
    from pathlib import Path

    static_lib = Path(__file__).parent / 'cylc_review/static'
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
    """Return a dict containing quick service server status."""
    ret = {}
    log_root_glob = os.path.expanduser(
        LOG_ROOT_TMPL
        % {
            "ns": service_cls.NS,
            "util": service_cls.UTIL,
            "host": "*",
            "port": "*",
        }
    )
    for filename in glob(log_root_glob):
        try:
            for line in Path(filename).read_text().split('\n'):
                key, value = line.strip().split("=", 1)
                ret[key] = value
            break
        except (IOError, ValueError):
            pass
    return ret


def get_util_home(*args):
    """Return CYLC_DIR or the dirname of sys.argv[0].

    If args are specified, they are added to the end of returned path.

    """
    return str(Path(__file__).parent / '/'.join(args))
