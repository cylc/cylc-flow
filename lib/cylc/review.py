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

"""cylc [info] review [OPTIONS] ARGS

Start/stop ad-hoc Cylc Review web service server for browsing users' suite
logs via an HTTP interface.

With no arguments, the status of the ad-hoc web service server is printed.

For 'cylc review start', if 'PORT' is not specified, port 8080 is used."""

import cherrypy
from fnmatch import fnmatch
from glob import glob
import jinja2
from jinja2 import select_autoescape
import json
import mimetypes
import os
import pwd
import re
import shlex
from sqlite3 import ProgrammingError, OperationalError
import tarfile
from tempfile import NamedTemporaryFile
from time import gmtime, strftime
import traceback
import urllib

from cylc.hostuserutil import get_host
from cylc.review_dao import CylcReviewDAO
from cylc.task_state import (
    TASK_STATUSES_ORDERED, TASK_STATUS_GROUPS)
from cylc.version import CYLC_VERSION
from cylc.ws import get_util_home
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager


CYLC8_TASK_STATUSES_ORDERED = [
    'expired',
    'failed',
    'preparing',
    'running',
    'submitted',
    'submit-failed',
    'succeeded',
    'waiting',
]


class CylcReviewService(object):

    """'Cylc Review Service."""

    NS = "cylc"
    UTIL = "review"
    TITLE = "Cylc Review"

    CYCLES_PER_PAGE = 100
    JOBS_PER_PAGE = 15
    JOBS_PER_PAGE_MAX = 300
    MIME_TEXT_PLAIN = "text/plain"
    REC_URL = re.compile(r"((https?):\/\/[^\s\(\)&\[\]\{\}]+)")
    SEARCH_MODE_REGEX = "REGEX"
    SEARCH_MODE_TEXT = "TEXT"
    SUITES_PER_PAGE = 100
    VIEW_SIZE_MAX = 10 * 1024 * 1024  # 10MB
    WORKFLOW_FILES = [
        'suite.rc',
        'suite.rc.processed',
        'flow.cylc',
        'rose-suite.info',
        'opt/rose-suite-cylc-install.conf'
    ]

    def __init__(self, *args, **kwargs):
        self.exposed = True
        self.suite_dao = CylcReviewDAO()
        self.logo = os.path.basename(
            get_util_home("doc", "src", "cylc-logo.png"))
        self.title = self.TITLE
        self.host_name = get_host()
        if self.host_name and "." in self.host_name:
            self.host_name = self.host_name.split(".", 1)[0]
        self.cylc_version = CYLC_VERSION
        # Autoescape markup to prevent code injection from user inputs.
        template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                get_util_home("lib", "cylc", "cylc-review", "template")),
            autoescape=select_autoescape(
                enabled_extensions=('html', 'xml'), default_for_string=True),
        )
        template_env.filters['urlise'] = self.url2hyperlink
        self.template_env = template_env

    @classmethod
    def url2hyperlink(cls, text):
        """Turn http or https link into a hyperlink."""
        return cls.REC_URL.sub(r'<a href="\g<1>">\g<1></a>', text)

    @cherrypy.expose
    def index(self, form=None):
        """Display a page to input user ID and suite ID."""
        data = {
            "logo": self.logo,
            "title": self.title,
            "host": self.host_name,
            "cylc_version": self.cylc_version,
            "script": cherrypy.request.script_name,
        }
        if form == "json":
            return json.dumps(data)
        try:
            return self.template_env.get_template("index.html").render(**data)
        except jinja2.TemplateError:
            traceback.print_exc()

    @cherrypy.expose
    def broadcast_states(self, user, suite, form=None):
        """List current broadcasts of a running or completed suite."""
        data = {
            "logo": self.logo,
            "title": self.title,
            "host": self.host_name,
            "user": user,
            "suite": suite,
            "cylc_version": self.cylc_version,
            "script": cherrypy.request.script_name,
            "method": "broadcast_states",
            "states": {},
            "time": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
        }
        data["states"].update(
            self.suite_dao.get_suite_state_summary(user, suite))
        data["states"]["last_activity_time"] = (
            self.get_last_activity_time(user, suite))
        data.update(self._get_suite_logs_info(user, suite))

        try:
            data["broadcast_states"] = (
                self.suite_dao.get_suite_broadcast_states(user, suite))
        except OperationalError:
            data["broadcast_states"] = ()

        if form == "json":
            return json.dumps(data)
        try:
            return self.template_env.get_template(
                "broadcast-states.html").render(**data)
        except jinja2.TemplateError:
            traceback.print_exc()
        return json.dumps(data)

    @cherrypy.expose
    def broadcast_events(self, user, suite, form=None):
        """List broadcasts history of a running or completed suite."""
        data = {
            "logo": self.logo,
            "title": self.title,
            "host": self.host_name,
            "user": user,
            "suite": suite,
            "cylc_version": self.cylc_version,
            "script": cherrypy.request.script_name,
            "method": "broadcast_events",
            "states": {},
            "time": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
        }
        data["states"].update(
            self.suite_dao.get_suite_state_summary(user, suite))
        data.update(self._get_suite_logs_info(user, suite))

        try:
            data["broadcast_events"] = (
                self.suite_dao.get_suite_broadcast_events(user, suite))
        except OperationalError:
            data["broadcast_events"] = ()

        if form == "json":
            return json.dumps(data)
        try:
            return self.template_env.get_template(
                "broadcast-events.html").render(**data)
        except jinja2.TemplateError:
            traceback.print_exc()
        return json.dumps(data)

    @cherrypy.expose
    def cycles(
            self, user, suite, page=1, order=None, per_page=None,
            no_fuzzy_time="0", form=None):
        """List cycles of a running or completed suite."""

        # Call to ensure user and suite args valid (together), else raise 404.
        self._get_user_suite_dir(user, suite)

        per_page_default = self.CYCLES_PER_PAGE
        if not isinstance(per_page, int):
            if per_page:
                per_page = int(per_page)
            else:
                per_page = per_page_default
        if page and per_page:
            page = int(page)
        else:
            page = 1
        data = {
            "logo": self.logo,
            "title": self.title,
            "host": self.host_name,
            "user": user,
            "suite": suite,
            "is_option_on": (
                order is not None and order != "time_desc" or
                per_page is not None and per_page != per_page_default
            ),
            "order": order,
            "cylc_version": self.cylc_version,
            "script": cherrypy.request.script_name,
            "method": "cycles",
            "no_fuzzy_time": no_fuzzy_time,
            "states": {},
            "per_page": per_page,
            "per_page_default": per_page_default,
            "page": page,
            "task_status_groups": TASK_STATUS_GROUPS,
        }
        data["entries"], data["of_n_entries"] = (
            self.suite_dao.get_suite_cycles_summary(
                user, suite, order, per_page, (page - 1) * per_page))
        if per_page:
            data["n_pages"] = data["of_n_entries"] / per_page
            if data["of_n_entries"] % per_page != 0:
                data["n_pages"] += 1
        else:
            data["n_pages"] = 1
        data.update(self._get_suite_logs_info(user, suite))
        data["states"].update(
            self.suite_dao.get_suite_state_summary(user, suite))
        data["states"]["last_activity_time"] = (
            self.get_last_activity_time(user, suite))
        data["time"] = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
        if form == "json":
            return json.dumps(data)
        try:
            return self.template_env.get_template("cycles.html").render(**data)
        except jinja2.TemplateError:
            traceback.print_exc()
        return json.dumps(data)

    @cherrypy.expose
    def taskjobs(
            self, user, suite, page=1, cycles=None, tasks=None,
            task_status=None, job_status=None,
            order=None, per_page=None, no_fuzzy_time="0", form=None):
        """List task jobs.

        user -- A string containing a valid user ID
        suite -- A string containing a valid suite ID
        page -- The page number to display
        cycles -- Display only task jobs matching these cycles. A value in the
                  list can be a cycle, the string "before|after CYCLE", or a
                  glob to match cycles.
        tasks -- Display only jobs for task names matching a list of names.
                 The list should be specified as a string which will be
                 shlex.split by this method. Values can be a valid task name or
                 a glob like pattern for matching valid task names.
        task_status -- Select by task statuses.
        job_status -- Select by job status. See
                      CylcReviewDAO.JOB_STATUS_COMBOS for detail.
        order -- Order search in a predetermined way. A valid value is one of
            "time_desc", "time_asc",
            "cycle_desc_name_desc", "cycle_desc_name_asc",
            "cycle_asc_name_desc", "cycle_asc_name_asc",
            "name_asc_cycle_asc", "name_desc_cycle_asc",
            "name_asc_cycle_desc", "name_desc_cycle_desc",
            "time_submit_desc", "time_submit_asc",
            "time_run_desc", "time_run_asc",
            "time_run_exit_desc", "time_run_exit_asc",
            "duration_queue_desc", "duration_queue_asc",
            "duration_run_desc", "duration_run_asc",
            "duration_queue_run_desc", "duration_queue_run_asc"
        per_page -- Number of entries to display per page (default=32)
        no_fuzzy_time -- Don't display fuzzy time if this is True.
        form -- Specify return format. If None, display HTML page. If "json",
                return a JSON data structure.
        """

        # Call to ensure user and suite args valid (together), else raise 404.
        self._get_user_suite_dir(user, suite)

        per_page_default = self.JOBS_PER_PAGE
        per_page_max = self.JOBS_PER_PAGE_MAX
        if not isinstance(per_page, int):
            if per_page:
                per_page = int(per_page)
            else:
                per_page = per_page_default
        is_option_on = (
            cycles or
            tasks or
            task_status or
            job_status or
            order is not None and order != "time_desc" or
            per_page != per_page_default
        )
        if page and per_page:
            page = int(page)
        else:
            page = 1

        # Set list of task states depending on Cylc version 7 or 8
        task_statuses_ordered = TASK_STATUSES_ORDERED
        try:
            if self.suite_dao.is_cylc8(user, suite):
                task_statuses_ordered = CYLC8_TASK_STATUSES_ORDERED
        except ProgrammingError:
            pass
        # get selected task states
        if not task_status:
            # default task statuses - if updating please also change the
            # $("#reset_task_statuses").click function in cylc-review.js
            task_status = list(task_statuses_ordered)
        elif not isinstance(task_status, list):
            task_status = [task_status]

        # generate list of all task states [(state, "0" or "1"), ...]
        task_statuses = [(status, "1" if status in task_status else "0")
                         for status in task_statuses_ordered]

        data = {
            "cycles": cycles,
            "host": self.host_name,
            "is_option_on": is_option_on,
            "logo": self.logo,
            "method": "taskjobs",
            "no_fuzzy_time": no_fuzzy_time,
            "task_statuses": task_statuses,
            "job_status": job_status,
            "order": order,
            "page": page,
            "per_page": per_page,
            "per_page_default": per_page_default,
            "per_page_max": per_page_max,
            "cylc_version": self.cylc_version,
            "script": cherrypy.request.script_name,
            "states": {},
            "suite": suite,
            "tasks": tasks,
            "task_status_groups": TASK_STATUS_GROUPS,
            "title": self.title,
            "user": user,
        }
        if cycles:
            cycles = shlex.split(str(cycles))
        if tasks:
            tasks = shlex.split(str(tasks))
        data.update(self._get_suite_logs_info(user, suite))
        data["states"].update(
            self.suite_dao.get_suite_state_summary(user, suite))
        data["states"]["last_activity_time"] = (
            self.get_last_activity_time(user, suite))
        entries, of_n_entries = self.suite_dao.get_suite_job_entries(
            user, suite, cycles, tasks, task_status, job_status, order,
            per_page, (page - 1) * per_page)
        data["entries"] = entries
        data["of_n_entries"] = of_n_entries
        if per_page:
            data["n_pages"] = of_n_entries / per_page
            if of_n_entries % per_page != 0:
                data["n_pages"] += 1
        else:
            data["n_pages"] = 1
        data["time"] = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
        if form == "json":
            return json.dumps(data)
        try:
            return self.template_env.get_template("taskjobs.html").render(
                **data)
        except jinja2.TemplateError:
            traceback.print_exc()

    @cherrypy.expose
    def jobs(self, user, suite, page=1, cycles=None, tasks=None,
             no_status=None, order=None, per_page=None, no_fuzzy_time="0",
             form=None):
        """(Deprecated) Redirect to self.taskjobs.

        Convert "no_status" to "task_status" argument of self.taskjobs.
        """
        task_status = None
        if no_status:
            task_status = []
            if not isinstance(no_status, list):
                no_status = [no_status]
            for key, values in TASK_STATUS_GROUPS.items():
                if key not in no_status:
                    task_status += values
        return self.taskjobs(
            user, suite, page, cycles, tasks, task_status,
            None, order, per_page, no_fuzzy_time, form)

    @cherrypy.expose
    def suites(self, user, names=None, page=1, order=None, per_page=None,
               no_fuzzy_time="0", form=None):
        """List (installed) suites of a user.

        user -- A string containing a valid user ID
        form -- Specify return format. If None, display HTML page. If "json",
                return a JSON data structure.

        """
        user_suite_dir_root = self._get_user_suite_dir_root(user)
        per_page_default = self.SUITES_PER_PAGE
        if not isinstance(per_page, int):
            if per_page:
                per_page = int(per_page)
            else:
                per_page = per_page_default
        if page and per_page:
            page = int(page)
        else:
            page = 1
        data = {
            "logo": self.logo,
            "title": self.title,
            "host": self.host_name,
            "cylc_version": self.cylc_version,
            "script": cherrypy.request.script_name,
            "method": "suites",
            "no_fuzzy_time": no_fuzzy_time,
            "user": user,
            "is_option_on": (
                names and shlex.split(str(names)) != ["*"] or
                order is not None and order != "time_desc" or
                per_page is not None and per_page != per_page_default
            ),
            "names": names,
            "page": page,
            "order": order,
            "per_page": per_page,
            "per_page_default": per_page_default,
            "entries": [],
        }
        name_globs = ["*"]
        if names:
            name_globs = shlex.split(str(names))
        # Get entries
        sub_names = [
            SuiteSrvFilesManager.DIR_BASE_SRV,
            "log",
            "share",
            "work"
        ]
        for dirpath, dnames, fnames in os.walk(
            user_suite_dir_root, followlinks=True
        ):
            if dirpath != user_suite_dir_root and (
                    any(name in dnames or name in fnames
                        for name in sub_names)):
                dnames[:] = []
            else:
                continue

            # Don't display the symlink to the latest version of
            # the Cylc8 Suite
            if re.match(r'.*runN$', dirpath):
                continue

            item = os.path.relpath(dirpath, user_suite_dir_root)
            if not any(fnmatch(item, glob_) for glob_ in name_globs):
                continue
            try:
                data["entries"].append({
                    "name": item,
                    "info": {},
                    "last_activity_time": (
                        self.get_last_activity_time(user, item))})
            except OSError:
                pass

        if order == "name_asc":
            data["entries"].sort(key=lambda entry: entry["name"])
        elif order == "name_desc":
            data["entries"].sort(key=lambda entry: entry["name"], reverse=True)
        elif order == "time_asc":
            data["entries"].sort(self._sort_summary_entries, reverse=True)
        else:  # order == "time_desc"
            data["entries"].sort(self._sort_summary_entries)
        data["of_n_entries"] = len(data["entries"])
        if per_page:
            data["n_pages"] = data["of_n_entries"] / per_page
            if data["of_n_entries"] % per_page != 0:
                data["n_pages"] += 1
            offset = (page - 1) * per_page
            data["entries"] = data["entries"][offset:offset + per_page]
        else:
            data["n_pages"] = 1

        # Get basic ros(i)e suite info (project and title) per entry if found
        for entry in data["entries"]:
            user_suite_dir = os.path.join(user_suite_dir_root, entry["name"])
            rosie_suite_info = os.path.join(user_suite_dir, "rose-suite.info")
            if os.path.isfile(rosie_suite_info):
                rosie_info = {}
                try:
                    for line in open(rosie_suite_info, 'r').readlines():
                        if not line.strip().startswith('#') and '=' in line:
                            rosie_key, rosie_val = line.strip().split("=", 1)
                            if rosie_key in ("project", "title"):
                                rosie_info[rosie_key] = rosie_val
                except IOError:
                    pass
                entry["info"].update(rosie_info)

        data["time"] = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
        if form == "json":
            return json.dumps(data)
        template = self.template_env.get_template("suites.html")
        return template.render(**data)

    def get_file(self, user, suite, path, path_in_tar=None, mode=None):
        """Returns file information / content or a cherrypy response."""
        suite = suite.replace('%2F', '/')
        f_name = self._get_user_suite_dir(user, suite, path)
        self._check_file_path(path)
        view_size_max = self.VIEW_SIZE_MAX
        if path_in_tar:
            tar_f = tarfile.open(f_name, "r:gz")
            try:
                tar_info = tar_f.getmember(path_in_tar)
            except KeyError:
                raise cherrypy.HTTPError(404)
            f_size = tar_info.size
            handle = tar_f.extractfile(path_in_tar)
            if handle.read(2) == "#!":
                mime = self.MIME_TEXT_PLAIN
            else:
                mime = mimetypes.guess_type(
                    urllib.pathname2url(path_in_tar))[0]
            handle.seek(0)
            if (mode == "download" or
                    f_size > view_size_max or
                    mime and
                    (not mime.startswith("text/") or mime.endswith("html"))):
                temp_f = NamedTemporaryFile()
                f_bsize = os.fstatvfs(temp_f.fileno()).f_bsize
                while True:
                    bytes_ = handle.read(f_bsize)
                    if not bytes_:
                        break
                    temp_f.write(bytes_)
                cherrypy.response.headers["Content-Type"] = mime
                try:
                    return cherrypy.lib.static.serve_file(temp_f.name, mime)
                finally:
                    temp_f.close()
            text = handle.read()
        else:
            f_size = os.stat(f_name).st_size
            if open(f_name).read(2) == "#!":
                mime = self.MIME_TEXT_PLAIN
            else:
                mime = mimetypes.guess_type(urllib.pathname2url(f_name))[0]
            if not mime:
                mime = self.MIME_TEXT_PLAIN
            if (mode == "download" or
                    f_size > view_size_max or
                    mime and
                    (not mime.startswith("text/") or mime.endswith("html"))):
                cherrypy.response.headers["Content-Type"] = mime
                return cherrypy.lib.static.serve_file(f_name, mime)
            text = open(f_name).read()
        try:
            if mode in [None, "text"]:
                text = jinja2.escape(text)
            lines = [unicode(line) for line in text.splitlines()]
        except UnicodeDecodeError:
            if path_in_tar:
                handle.seek(0)
                # file closed by cherrypy
                return cherrypy.lib.static.serve_fileobj(
                    handle, self.MIME_TEXT_PLAIN)
            else:
                return cherrypy.lib.static.serve_file(
                    f_name, self.MIME_TEXT_PLAIN)
        else:
            if path_in_tar:
                handle.close()
        name = path
        if path_in_tar:
            name = "log/" + path_in_tar
        job_entry = None
        if name.startswith("log/job"):
            names = name.replace("log/job/", "").split("/", 3)
            if len(names) == 4:
                cycle, task, submit_num, _ = names
                entries = self.suite_dao.get_suite_job_entries(
                    user, suite, [cycle], [task],
                    None, None, None, None, None)[0]
                for entry in entries:
                    if entry["submit_num"] == int(submit_num):
                        job_entry = entry
                        break
        if (
            fnmatch(os.path.basename(path), "suite*.rc*")
            or fnmatch(os.path.basename(path), "*.cylc")
        ):
            file_content = "cylc-suite-rc"
        elif fnmatch(os.path.basename(path), "rose*.conf"):
            file_content = "rose-conf"
        else:
            file_content = None

        return lines, job_entry, file_content, f_name

    def get_last_activity_time(self, user, suite):
        """Returns last activity time for a suite based on database stat"""
        for name in [os.path.join("log", "db"), "cylc-suite.db"]:
            fname = os.path.join(self._get_user_suite_dir(user, suite), name)
            try:
                return strftime(
                    "%Y-%m-%dT%H:%M:%SZ", gmtime(os.stat(fname).st_mtime))
            except OSError:
                continue

    @cherrypy.expose
    def viewsearch(self, user, suite, path=None, path_in_tar=None, mode=None,
                   search_string=None, search_mode=None):
        """Search a text log file."""
        # get file or serve raw
        file_output = self.get_file(
            user, suite, path, path_in_tar=path_in_tar, mode=mode)
        if isinstance(file_output, tuple):
            lines, _, file_content, _ = self.get_file(
                user, suite, path, path_in_tar=path_in_tar, mode=mode)
        else:
            return file_output

        template = self.template_env.get_template("view-search.html")

        if search_string:
            results = []
            line_numbers = []

            # perform search
            for i, line in enumerate(lines):
                if search_mode is None or search_mode == self.SEARCH_MODE_TEXT:
                    match = line.find(search_string)
                    if match == -1:
                        continue
                    start = match
                    end = start + len(search_string)
                elif search_mode == self.SEARCH_MODE_REGEX:
                    match = re.search(search_string, line)
                    if not match:
                        continue
                    start, end = match.span()
                else:
                    # ERROR: un-recognised search_mode
                    break
                # if line matches search string include in results
                results.append([line[:start], line[start:end],
                                line[end:]])
                if mode in [None, "text"]:
                    line_numbers.append(i + 1)  # line numbers start from 1
            lines = results
        else:
            # no search is being performed, client is requesting the whole
            # page
            if mode in [None, "text"]:
                line_numbers = range(1, len(lines) + 1)
            else:
                line_numbers = []
            lines = [[line] for line in lines]

        return template.render(
            lines=lines,
            line_numbers=line_numbers,
            file_content=file_content
        )

    @cherrypy.expose
    def view(self, user, suite, path, path_in_tar=None, mode=None,
             no_fuzzy_time="0"):
        """View a text log file."""
        # Log files with +TZ in name end up with space instead of plus sign, so
        # put plus sign back in (https://github.com/cylc/cylc-flow/issues/4260)
        path = re.sub(r"(log\.\S+\d{2})\s(\d{2,4})$", r"\1+\2", path)
        suite = suite.replace('%2F', '/')

        # get file or serve raw data
        file_output = self.get_file(
            user, suite, path, path_in_tar=path_in_tar, mode=mode)
        if isinstance(file_output, tuple):
            lines, job_entry, file_content, f_name = self.get_file(
                user, suite, path, path_in_tar=path_in_tar, mode=mode)
        else:
            return file_output

        template = self.template_env.get_template("view.html")

        data = {}
        data.update(self._get_suite_logs_info(user, suite))
        return template.render(
            cylc_version=self.cylc_version,
            script=cherrypy.request.script_name,
            method="view",
            time=strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
            logo=self.logo,
            title=self.title,
            host=self.host_name,
            user=user,
            suite=suite,
            path=path,
            path_in_tar=path_in_tar,
            f_name=f_name,
            mode=mode,
            no_fuzzy_time=no_fuzzy_time,
            file_content=file_content,
            lines=lines,
            entry=job_entry,
            task_status_groups=TASK_STATUS_GROUPS,
            **data)

    def _get_suite_logs_info(self, user, suite):
        """Return a dict of suite-related files including suite logs."""
        data = {"files": {}}
        user_suite_dir = self._get_user_suite_dir(user, suite)  # cylc files

        # Rose files: to recognise & group, but not process, standard formats
        data["files"]["rose"] = {}

        # Rosie suite info
        info_name = os.path.join(user_suite_dir, "rose-suite.info")
        if os.path.isfile(info_name):
            stat = os.stat(info_name)
            data["files"]["rose"]["rose-suite.info"] = {
                "path": "rose-suite.info",
                "mtime": stat.st_mtime,
                "size": stat.st_size}

        # Get Rose log files
        for key in ["conf", "log", "version"]:
            f_name = os.path.join(user_suite_dir, "log/rose-suite-run." + key)
            if os.path.isfile(f_name):
                stat = os.stat(f_name)
                data["files"]["rose"]["log/rose-suite-run." + key] = {
                    "path": "log/rose-suite-run." + key,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size}
        for key in ["html", "txt", "version"]:
            for f_name in glob(os.path.join(user_suite_dir, "log/*." + key)):
                if os.path.basename(f_name).startswith("rose-"):
                    continue
                name = os.path.join("log", os.path.basename(f_name))
                stat = os.stat(f_name)
                data["files"]["rose"]["other:" + name] = {
                    "path": name,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size}

        # Returns a tuple that looks like:
        #    ("cylc-run",
        #     {"err": {"path": "log/suite/err", "mtime": mtime, "size": size},
        #      "log": {"path": "log/suite/log", "mtime": mtime, "size": size},
        #      "out": {"path": "log/suite/out", "mtime": mtime, "size": size}})
        logs_info = {}
        prefix = "~"
        if user:
            prefix += user
        d_rel = os.path.join("cylc-run", suite)
        dir_ = os.path.expanduser(os.path.join(prefix, d_rel))

        # Get cylc files
        for key in self.WORKFLOW_FILES:
            f_name = os.path.join(dir_, key)
            if os.path.isfile(f_name):
                f_stat = os.stat(f_name)
                logs_info[key] = {"path": key,
                                  "mtime": f_stat.st_mtime,
                                  "size": f_stat.st_size}

        # Get cylc suite/workflow log files and other files:
        EXTRA_FILES = [
            "log/workflow/log*",
            "log/workflow/file-installation-log.*",
            "log/suite/log*",
            "log/suite/file-installation-log.*",
            "log/install/*",
            "log/flow-config/*",
            "log/config/*",
            "log/scheduler/*.log",
            "log/remote-install/*.log"
        ]
        for glob_pattern in EXTRA_FILES:
            for f_name in glob(os.path.join(dir_, glob_pattern)):
                key = os.path.relpath(f_name, dir_)
                f_stat = os.stat(f_name)
                logs_info[key] = {
                    "path": key,
                    "mtime": f_stat.st_mtime,
                    "size": f_stat.st_size
                }

        data["files"]["cylc"] = logs_info
        return data

    @classmethod
    def _check_dir_access(cls, path):
        """Check directory is accessible.

        Raises:
            - cherrypy.HTTPError(404) if path does not exist
            - cherrypy.HTTPError(403) if path not accessible

        Return path on success.

        """
        if not os.path.exists(path):
            raise cherrypy.HTTPError(
                404, 'Path {path} does not exist'.format(path=path))
        if not os.access(path, os.R_OK):
            raise cherrypy.HTTPError(403)
        return path

    @staticmethod
    def _get_user_home(user):
        """Return, e.g. ~/cylc-run/ for a cylc suite.

        N.B. os.path.expanduser does not fail if ~user is invalid.

        Raises:
            cherrypy.HTTPError(404)

        """
        try:
            return pwd.getpwnam(user).pw_dir
        except KeyError:
            raise cherrypy.HTTPError(404)

    def _get_user_suite_dir_root(self, user):
        """Return, e.g. ~user/cylc-run/ for a cylc suite."""
        return self._check_dir_access(os.path.join(
            self._get_user_home(user),
            "cylc-run"))

    @staticmethod
    def _check_string_for_path(string):
        """Raise HTTP 403 error if the provided string contain path chars.

        Examples:
            >>> CylcReviewService._check_string_for_path(
            ...     os.path.join('foo', 'bar'))
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)

        Raises:
            cherrypy.HTTPError(403)

        """
        if os.path.split(string)[0] != '':
            raise cherrypy.HTTPError(403)

    @classmethod
    def _check_file_path(cls, path):
        """Raise HTTP 403 error if the path is not intended to be served.

        Examples:
            >>> CylcReviewService._check_file_path('.service/contact')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> CylcReviewService._check_file_path('log/../.service/contact')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> CylcReviewService._check_file_path('log/foo')  # pass, etc.
            >>> CylcReviewService._check_file_path('suite.rc')
            >>> CylcReviewService._check_file_path('suite.rc.processed')

        Raises:
            cherrypy.HTTPError(403)

        Whitelist paths:
            Paths in cls.WORKFLOW_FILES

        Blacklist non-normalised paths - see ``_check_path_normalised``.

        """
        cls._check_path_normalised(path)
        # Get rootdir and sub-path.
        head, tail = os.path.split(path)
        while os.path.dirname(head) not in ['', os.sep]:
            head, tail1 = os.path.split(head)
            tail = os.path.join(tail1, tail)
        if not (
            head == 'log' or
            (not head and tail in cls.WORKFLOW_FILES) or
            (head, tail) == (u'opt', u'rose-suite-cylc-install.conf')
        ):
            raise cherrypy.HTTPError(403)

    @staticmethod
    def _check_path_normalised(path):
        """Raise HTTP 403 error if path is not normalised.

        Examples:
            >>> CylcReviewService._check_path_normalised('foo//bar')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> CylcReviewService._check_path_normalised('foo/bar/')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> CylcReviewService._check_path_normalised('foo/./bar')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> CylcReviewService._check_path_normalised('foo/../bar')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> CylcReviewService._check_path_normalised('../foo')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)

        Raises:
            cherrypy.HTTPError(403)

        """
        path = os.path.join('foo', path)  # Enable checking of ../foo paths.
        if os.path.normpath(path) != path:
            raise cherrypy.HTTPError(403)

    def _get_user_suite_dir(self, user, suite, *paths):
        """Return, e.g. ~user/cylc-run/suite/... for a cylc suite.

        Raises:
            - cherrypy.HTTPError(404) if path does not exist
            - cherrypy.HTTPError(403) if path not accessible

        """
        self._check_string_for_path(user)
        self._check_path_normalised(suite)
        for path in paths:
            self._check_path_normalised(path)
        suite_dir = os.path.join(
            self._get_user_home(user),
            "cylc-run",
            suite)
        if not paths:
            return self._check_dir_access(suite_dir)
        path = os.path.join(suite_dir, *paths)
        if not path.startswith(suite_dir):
            # Raise HTTP 403 if path lies outside of the suite directory. Note:
            # >>> os.path.join('/foo', '/bar')
            # '/bar'
            raise cherrypy.HTTPError(403)
        return self._check_dir_access(path)

    @staticmethod
    def _sort_summary_entries(suite1, suite2):
        """Sort suites by last_activity_time."""
        return (cmp(suite2.get("last_activity_time"),
                    suite1.get("last_activity_time")) or
                cmp(suite1["name"], suite2["name"]))
