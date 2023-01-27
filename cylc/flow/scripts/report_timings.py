#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

"""cylc report-timings [OPTIONS] ARGS

Display workflow timing information.

Retrieve workflow timing information for wait and run time performance
analysis. Raw output and summary output (in text or HTML format) are available.
Output is sent to standard output, unless an output filename is supplied.

Summary Output (the default):
  Data stratified by host and job runner that provides a statistical
  summary of:
    1. Queue wait time (duration between task submission and start times)
    2. Task run time (duration between start and succeed times)
    3. Total run time (duration between task submission and succeed times)
  Summary tables can be output in plain text format, or HTML with embedded SVG
  boxplots.  Both summary options require the Pandas library, and the HTML
  summary option requires the Matplotlib library.

Raw Output:
  A flat list of tabular data that provides (for each task and cycle) the
    1. Time of successful submission
    2. Time of task start
    3. Time of task successful completion
  as well as information about the job runner and remote host to permit
  stratification/grouping if desired by downstream processors.

Timings are shown only for succeeded tasks.

For long-running or large workflows (i.e. workflows with many task events),
the database query to obtain the timing information may take some time.
"""

import collections
import contextlib
import io as StringIO
import sys
from typing import TYPE_CHECKING

from cylc.flow.exceptions import CylcError
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.pathutil import get_workflow_run_pub_db_path
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


@contextlib.contextmanager
def smart_open(filename=None):
    """
    Allow context management for output to either a file or
    to standard output transparently.

    See https://stackoverflow.com/a/17603000

    """
    if filename and filename != '-':
        fh = open(filename, 'w')  # noqa SIM115 (close done in finally block)
    else:
        fh = sys.stdout
    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[WORKFLOW_ID_ARG_DOC]
    )
    parser.add_option(
        "-r", "--raw",
        help="Show raw timing output suitable for custom diagnostics.",
        action="store_true", default=False, dest="show_raw"
    )
    parser.add_option(
        "-s", "--summary",
        help="Show textual summary timing output for tasks.",
        action="store_true", default=False, dest="show_summary"
    )
    parser.add_option(
        "-w", "--web-summary",
        help="Show HTML summary timing output for tasks.",
        action="store_true", default=False, dest="html_summary"
    )
    parser.add_option(
        "-O", "--output-file",
        help="Output to a specific file",
        action="store", default=None, dest="output_filename")

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
    )

    output_options = [
        options.show_raw, options.show_summary, options.html_summary
    ]
    if output_options.count(True) > 1:
        parser.error('Cannot combine output formats (choose one)')
    if not any(output_options):
        # No output specified - choose summary by default
        options.show_summary = True

    with _get_dao(workflow_id) as dao:
        row_buf = format_rows(*dao.select_task_times())
    with smart_open(options.output_filename) as output:
        if options.show_raw:
            output.write(row_buf.getvalue())
        else:
            summary: TimingSummary
            if options.show_summary:
                summary = TextTimingSummary(row_buf)
            elif options.html_summary:
                summary = HTMLTimingSummary(row_buf)
            summary.write_summary(output)


def format_rows(header, rows):
    """Write the rows in tabular format to a string buffer.

    Ensure that each column is wide enough to contain the widest data
    value and the widest header value.

    """
    sio = StringIO.StringIO()
    max_lengths = [
        max(data_len, head_len)
        for data_len, head_len in zip(
            (max(len(r[i]) for r in rows) for i in range(len(header))),
            (len(h) for h in header)
        )
    ]
    formatter = ' '.join('%%-%ds' % line for line in max_lengths) + '\n'
    sio.write(formatter % header)
    for r in rows:
        sio.write(formatter % r)
    sio.seek(0)
    return sio


def _get_dao(workflow):
    """Return the DAO (public) for workflow."""
    return CylcWorkflowDAO(
        get_workflow_run_pub_db_path(workflow), is_public=True)


class TimingSummary:
    """Base class for summarizing timing output from cylc.flow run database."""

    def __init__(self, filepath_or_buffer=None):
        """Set up internal dataframe storage for time durations."""

        self._check_imports()
        if filepath_or_buffer is not None:
            self.read_timings(filepath_or_buffer)
        else:
            self.df = None
            self.by_host_and_job_runner = None

    def read_timings(self, filepath_or_buffer):
        """
        Set up time duration dataframe storage based on start/stop/succeed
        times from flat database output.

        """
        import pandas as pd

        # Avoid truncation of content in columns.
        pd.set_option('display.max_colwidth', 10000)

        df = pd.read_csv(
            filepath_or_buffer, delim_whitespace=True, index_col=[0, 1, 2, 3],
            parse_dates=[4, 5, 6]
        )
        self.df = pd.DataFrame({
            'queue_time': (
                df['start_time'] - df['submit_time']).apply(self._dt_to_s),
            'run_time': (
                df['succeed_time'] - df['start_time']).apply(self._dt_to_s),
            'total_time': (
                df['succeed_time'] - df['submit_time']).apply(self._dt_to_s),
        })
        self.df = self.df.rename_axis('timing_category', axis='columns')
        self.by_host_and_job_runner = self.df.groupby(
            level=['host', 'job_runner']
        )

    def write_summary(self, buf=None):
        """Using the stored timings dataframe, output the data summary."""

        if buf is None:
            buf = sys.stdout
        self.write_summary_header(buf)
        for group, df in self.by_host_and_job_runner:
            self.write_group_header(buf, group)
            df_reshape = self._reshape_timings(df)
            df_describe = df.groupby(level='name').describe()
            if df_describe.index.nlevels > 1:
                df_describe = df_describe.unstack()  # for pandas < 0.20.0
            df_describe.index.rename(None, inplace=True)
            for timing_category in self.df.columns:
                self.write_category(
                    buf, timing_category, df_reshape, df_describe
                )
        self.write_summary_footer(buf)

    def write_summary_header(self, buf):
        pass

    def write_summary_footer(self, buf):
        pass

    def write_group_header(self, buf, group):
        pass

    def write_category(self, buf, category, df_reshape, df_describe):
        pass

    def _check_imports(self):
        try:
            import pandas
        except ImportError:
            raise CylcError('Cannot import pandas - summary unavailable.')
        else:
            del pandas

    @staticmethod
    def _reshape_timings(timings):
        """
        Given a dataframe of timings returned from the Cylc DAO methods
        indexed by (task, cycle point, ...) with columns for the various
        timing categories, return a dataframe reshaped with an index of
        (timing category, cycle point, ...) with columns for each task.

        Need a special method rather than standard Pandas pivot-table
        to handle duplicated index entries properly.

        """
        if timings.index.duplicated().any():
            # The 'unstack' used to pivot the dataframe gives an error if
            # there are duplicate entries in the index (see #2509).  The
            # best way around this seems to be to add an intermediate index
            # level (in this case a retry counter) to de-duplicate indices.
            counts = collections.defaultdict(int)
            retry = []
            for t in timings.index:
                counts[t] += 1
                retry.append(counts[t])
            timings = timings.assign(retry=retry)
            timings = timings.set_index('retry', append=True)

        return timings.unstack('name').stack(level=0)

    @staticmethod
    def _dt_to_s(dt):
        import pandas as pd
        try:
            return dt.total_seconds()
        except AttributeError:
            # Older versions of pandas have the timedelta as a numpy
            # timedelta64 type, which didn't support total_seconds
            return pd.Timedelta(dt).total_seconds()


class TextTimingSummary(TimingSummary):
    """Timing summary in text form."""

    line_width = 80

    def write_group_header(self, buf, group):
        title = 'Host: %s\tJob Runner: %s' % group
        buf.write('=' * self.line_width + '\n')
        buf.write(title.center(self.line_width - 1) + '\n')
        buf.write('=' * self.line_width + '\n')

    def write_category(self, buf, category, df_reshape, df_describe):
        buf.write(category.center(self.line_width) + '\n')
        buf.write(('-' * len(category)).center(self.line_width) + '\n')
        buf.write(df_describe[category].to_string())
        buf.write('\n\n')


class HTMLTimingSummary(TimingSummary):
    """Timing summary in HTML form."""

    def write_summary_header(self, buf):
        css = """
            body {
                font-family: Sans-Serif;
                text-align: center;
            }
            h1 {
                background-color: grey;
            }
            h2 {
                width: 85%;
                background-color: #f0f0f0;
                margin: auto;
            }
            table {
                width: 75%;
                margin: auto;
                border-collapse: collapse;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            td {
                text-align: right;
            }
            th, td {
                border-bottom: 1px solid grey;
            }
            svg {
                width: 65%;
                height: auto;
                margin: auto;
                display: block;
            }
            .timing {
                padding-bottom: 40px;
            }
        """

        buf.write('<html><head><style>%s</style></head><body>' % css)

    def write_summary_footer(self, buf):
        buf.write('</body></html>')

    def write_group_header(self, buf, group):
        buf.write('<h1>Timings for host %s using job runner %s</h1>' % group)

    def write_category(self, buf, category, df_reshape, df_describe):
        import matplotlib.pyplot as plt
        buf.write('<div class="timing" id=%s>' % category)
        buf.write('<h2>%s</h2>\n' % (category.replace('_', ' ').title()))
        ax = (
            df_reshape
            .xs(category, level='timing_category')
            .plot(kind='box', vert=False)
        )
        ax.invert_yaxis()
        ax.set_xlabel('Seconds')
        plt.tight_layout()
        plt.gcf().savefig(buf, format='svg')
        try:
            table = df_describe[category].to_html(
                classes="summary", index_names=False, border=0
            )
        except TypeError:
            # older pandas don't support the "border" argument
            # so explicitly remove it
            table = df_describe[category].to_html(
                classes="summary", index_names=False
            )
            table = table.replace('border="1"', '')
        buf.write(table)
        buf.write('</div>')
        pass

    def _check_imports(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
        except ImportError:
            raise CylcError(
                'Cannot import matplotlib - HTML summary unavailable.'
            )
        super(HTMLTimingSummary, self)._check_imports()
