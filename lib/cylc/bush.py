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

"""Web service for browsing users' suite logs via an HTTP interface."""

import cherrypy
from fnmatch import fnmatch
from glob import glob
import jinja2
import json
import mimetypes
import os
import pwd
import re
import shlex
import sys
import tarfile
from tempfile import NamedTemporaryFile
from time import gmtime, strftime
import traceback
import urllib

from cylc.version import CYLC_VERSION
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.hostuserutil import get_host
from cylc.rundb import CylcSuiteDAO
from cylc.task_state import (
    TASK_STATUSES_ORDERED, TASK_STATUS_GROUPS)


class CylcBushService(object):

    """'cylc bush' Service."""

    NS = "cylc"
    UTIL = "cylc bush"
    TITLE = "cylc bush"

    CYCLES_PER_PAGE = 100
    JOBS_PER_PAGE = 15
    JOBS_PER_PAGE_MAX = 300
    MIME_TEXT_PLAIN = "text/plain"
    REC_URL = re.compile(r"((https?):\/\/[^\s\(\)&\[\]\{\}]+)")
    SEARCH_MODE_REGEX = "REGEX"
    SEARCH_MODE_TEXT = "TEXT"
    SUITES_PER_PAGE = 100
    VIEW_SIZE_MAX = 10 * 1024 * 1024  # 10MB

    def __init__(self, *args, **kwargs):
        self.exposed = True
        self.suite_dao = CylcSuiteDAO()
        conf = GLOBAL_CFG
        self.logo = conf.get_value(["cylc-bush", "logo"])
        self.title = conf.get_value(["cylc-bush", "title"], self.TITLE)
        self.host_name = conf.get_value(["cylc-bush", "host"])
        if self.host_name is None:
            self.host_name = get_host()
            if self.host_name and "." in self.host_name:
                self.host_name = self.host_name.split(".", 1)[0]
        self.cylc_version = CYLC_VERSION

        try:
            value = os.environ["CYLC_HOME"]
        except KeyError:
            value = os.path.abspath(__file__)
            for _ in range(4):
                value = os.path.dirname(value)
        return os.path.join(value, *args)


        template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(
            get_util_home("lib", "html", "template", "rose-bush")))
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
        data["broadcast_states"] = (
            self.suite_dao.get_suite_broadcast_states(user, suite))
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
        data["broadcast_events"] = (
            self.suite_dao.get_suite_broadcast_events(user, suite))
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
        conf = GLOBAL_CFG
        per_page_default = int(conf.get_value(
            ["rose-bush", "cycles-per-page"], self.CYCLES_PER_PAGE))
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
        job_status -- Select by job status. See RoseBushDAO.JOB_STATUS_COMBOS
                      for detail.
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
        per_page -- Number of entries to display per page (defualt=32)
        no_fuzzy_time -- Don't display fuzzy time if this is True.
        form -- Specify return format. If None, display HTML page. If "json",
                return a JSON data structure.

        """
        conf = GLOBAL_CFG
        per_page_default = int(conf.get_value(
            ["rose-bush", "jobs-per-page"], self.JOBS_PER_PAGE))
        per_page_max = int(conf.get_value(
            ["rose-bush", "jobs-per-page-max"], self.JOBS_PER_PAGE_MAX))
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
        task_statuses = (
            [[item, ""] for item in TASK_STATUSES_ORDERED])
        if task_status:
            if not isinstance(task_status, list):
                task_status = [task_status]
        for item in task_statuses:
            if not task_status or item[0] in task_status:
                item[1] = "1"
        all_task_statuses = all([status[1] == "1" for status in task_statuses])
        if all_task_statuses:
            task_status = []
        data = {
            "cycles": cycles,
            "host": self.host_name,
            "is_option_on": is_option_on,
            "logo": self.logo,
            "method": "taskjobs",
            "no_fuzzy_time": no_fuzzy_time,
            "all_task_statuses": all_task_statuses,
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
        conf = GLOBAL_CFG
        per_page_default = int(conf.get_value(
            ["rose-bush", "suites-per-page"], self.SUITES_PER_PAGE))
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
            ".service", "log", "share", "work", "suite.rc"]
        for dirpath, dnames, fnames in os.walk(
                user_suite_dir_root, followlinks=True):
            if dirpath != user_suite_dir_root and (
                    any(name in dnames or name in fnames
                        for name in sub_names)):
                dnames[:] = []
            else:
                continue
            item = os.path.relpath(dirpath, user_suite_dir_root)
            if not any(fnmatch(item, glob_) for glob_ in name_globs):
                continue
            try:
                data["entries"].append({
                    "name": item,
                    "last_activity_time": (
                        self.get_last_activity_time(user, item))})
            except OSError:
                continue

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
        # Get suite info for each entry
        for entry in data["entries"]:
            user_suite_dir = os.path.join(user_suite_dir_root, entry["name"])
        data["time"] = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
        if form == "json":
            return json.dumps(data)
        template = self.template_env.get_template("suites.html")
        return template.render(**data)

    def get_file(self, user, suite, path, path_in_tar=None, mode=None):
        """Returns file information / content or a cherrypy response."""
        f_name = self._get_user_suite_dir(user, suite, path)
        conf = GLOBAL_CFG
        view_size_max = int(conf.get_value(
            ["rose-bush", "view-size-max"], self.VIEW_SIZE_MAX))
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
        if fnmatch(os.path.basename(path), "suite*.rc*"):
            file_content = "cylc-suite-rc"

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
        # get file or serve raw data
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
                    # ERROR: un-reccognised search_mode
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
        """Return a dict with suite logs."""
        data = {"info": {}, "files": {}}
        user_suite_dir = self._get_user_suite_dir(user, suite)

        # Other recognised formats
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

        k, logs_info = self.suite_dao.get_suite_logs_info(user, suite)
        data["files"][k] = logs_info

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
            raise cherrypy.HTTPError(404)
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
            >>> RoseBushService._check_string_for_path(
            ...     os.path.join('foo', 'bar'))
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)

        Raises:
            cherrypy.HTTPError(403)

        """
        if os.path.split(string)[0] != '':
            raise cherrypy.HTTPError(403)

    @staticmethod
    def _check_path_normalised(path):
        """Raise HTTP 403 error if path is not normalised.

        Examples:
            >>> RoseBushService._check_path_normalised('foo//bar')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> RoseBushService._check_path_normalised('foo/bar/')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> RoseBushService._check_path_normalised('foo/./bar')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> RoseBushService._check_path_normalised('foo/../bar')
            Traceback (most recent call last):
             ...
            HTTPError: (403, None)
            >>> RoseBushService._check_path_normalised('../foo')
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

    @staticmethod
    def get_util_home(*args):
        """Return CYLC_HOME or the dirname of the dirname of sys.argv[0].

        If args are specified, they are added to the end of returned path.

        """
        try:
            value = os.environ["CYLC_HOME"]
        except KeyError:
            value = os.path.abspath(__file__)
            for _ in range(3):  # assume __file__ under $CYLC_HOME/lib/cylc/
                value = os.path.dirname(value)
        return os.path.join(value, *args)


if __name__ == "__main__":
    from cylc.ws import ws_cli
    ws_cli(CylcBushService)
elif 'doctest' not in sys.argv[0]:
    # If called as a module but not by the doctest module.
    from cylc.ws import wsgi_app
    application = wsgi_app(CylcBushService)
