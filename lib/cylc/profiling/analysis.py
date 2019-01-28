# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Module for performing analysis on profiling results and generating plots."""

import os
import re
import sys

# Import modules required for plotting if available.
try:
    import numpy
    import warnings
    warnings.simplefilter('ignore', numpy.RankWarning)
    import matplotlib.cm as colour_map
    import matplotlib.pyplot as plt
    CAN_PLOT = True
except (ImportError, RuntimeError):
    CAN_PLOT = False

from cylc.wallclock import get_unix_time_from_time_string

from . import (PROFILE_MODE_TIME, PROFILE_MODE_CYLC, SUMMARY_LINE_REGEX,
               MEMORY_LINE_REGEX, LOOP_MEMORY_LINE_REGEX, SLEEP_FUNCTION_REGEX,
               SUITE_STARTUP_STRING, PROFILE_MODES, PROFILE_FILES, METRICS,
               METRIC_TITLE, METRIC_UNIT, METRIC_FILENAME, METRIC_FIELDS,
               QUICK_ANALYSIS_METRICS)
from .git import (order_versions_by_date, describe)


def mean(data):
    """Return the mean average of a list of numbers."""
    return sum(data) / float(len(data))


def remove_profile_from_versions(versions):
    """Handles any versions with "-profile" in the version_name.

    Removes -profile* from the version name then sorts the versions by date
    (using the new version names).
    """
    ret = list(versions)
    flag = False
    temp = {}
    for version in ret:
        try:
            # Remove -profile from version_name if present.
            ind = version['name'].index('-profile')
            version['name'] = version['name'][:ind]
            version_id = describe(version['name'])
            # Temporally change the version_id to match the version_name.
            if version_id:
                temp[version['name']] = version['id']
                version['id'] = version_id
        except ValueError:
            continue
        else:
            flag = True
    if flag:
        # Sort versions by date.
        order_versions_by_date(ret)
        # Revert version_ids.
        for version in ret:
            if version['name'] in temp:
                version['id'] = temp[version['name']]
        return ret
    # No -profile versions, return the original list.
    return versions


def extract_results(result_file_dict, exp):
    """Extract results from the result files output by each run."""
    validate_mode = exp.get('validate_mode', False)
    profile_modes = [PROFILE_MODES[mode] for mode in exp['profile modes']]

    results = {}
    data = {}
    for run_name, result_files in result_file_dict.items():
        data[run_name] = []
        for result_file in result_files:
            profiling_results = {}
            if PROFILE_MODE_TIME in profile_modes:
                profiling_results.update(process_time_file(
                    result_file + PROFILE_FILES['time-err']))
            if PROFILE_MODE_CYLC in profile_modes:
                suite_start_time = None
                if not validate_mode:
                    suite_start_time = get_startup_time(
                        result_file + PROFILE_FILES['startup'])
                profiling_results.update(process_out_file(
                    result_file + PROFILE_FILES['cmd-out'], suite_start_time,
                    validate_mode))
            data[run_name].append(profiling_results)

    results = process_results(data)
    return results


def get_startup_time(file_name):
    """Return the value of the "SUITE STARTUP" entry as a string."""
    with open(file_name, 'r') as startup_file:
        return re.search('SUITE STARTUP: (.*)',
                         startup_file.read().decode()).groups()[0]


def process_time_file(file_name):
    """Extracts results from a result file generated using the /usr/bin/time
    profiler."""
    with open(file_name, 'r') as time_file:
        ret = {}
        for line in time_file:
            try:
                field, value = line.strip().rsplit(': ', 1)
            except ValueError:
                print('ERROR: Could not parse line "%s"' % line.strip())
                continue
            try:  # Try to cast as integer.
                ret[field] = int(value)
            except ValueError:
                try:  # Try to cast as float.
                    ret[field] = float(value)
                except ValueError:
                    if value.endswith('%'):  # Remove trailing % symbol
                        try:  # Try to cast as integer.
                            ret[field] = int(value[:-1])
                        except ValueError:  # Try to cast as float.
                            ret[field] = float(value[:-1])
                    elif ':' in value:  # Is a time of form h:m:s or m:s
                        seconds = 0.
                        increment = 1.
                        for time_field in reversed(value.split(':')):
                            seconds += float(time_field) * increment
                            increment *= 60
                        ret[field] = seconds
                    else:  # Cannot parse.
                        if 'Command being timed' not in line:
                            print('ERROR: Could not parse value "%s"' % line)
                            ret[field] = value
        if sys.platform == 'darwin':  # MacOS
            ret['total cpu time'] = (ret['user'] + ret['sys'])
        else:  # Assume Linux
            ret['total cpu time'] = (ret['User time (seconds)'] +
                                     ret['System time (seconds)'])
        return ret


def process_out_file(file_name, suite_start_time, validate=False):
    """Extract data from the out log file."""
    if not os.path.exists(file_name):
        sys.exit('No file with path {0}'.format(file_name))
    with open(file_name, 'r') as out_file:
        ret = {}
        lines = out_file.readlines()

        # Get start time.
        if lines[0].startswith(SUITE_STARTUP_STRING):
            ret['suite start time'] = float(
                lines[0][len(SUITE_STARTUP_STRING):])

        # Scan through log entries.
        ret['memory'] = []
        loop_mem_entries = []
        for line in lines:
            # Profile summary.
            match = SUMMARY_LINE_REGEX.search(line)
            if match:
                ret['function calls'] = int(match.groups()[0])
                ret['primitive function calls'] = int(match.groups()[1])
                ret['cpu time'] = float(match.groups()[2])
                continue

            # Memory info.
            match = MEMORY_LINE_REGEX.search(line)
            if match:
                memory, module, checkpoint = tuple(match.groups())
                ret['memory'].append((module, checkpoint, int(memory),))

                # Main loop memory info.
                if not validate:
                    match = LOOP_MEMORY_LINE_REGEX.search(checkpoint)
                    if match:
                        loop_no, time_str = match.groups()
                        loop_mem_entries.append((
                            int(loop_no),
                            int(get_unix_time_from_time_string(time_str)),
                        ))
                continue

            # Sleep time.
            match = SLEEP_FUNCTION_REGEX.search(line)
            if match:
                ret['sleep time'] = float(match.groups()[0])
                continue

        # Number of loops.
        if not validate:
            ret['loop count'] = loop_mem_entries[-1][0]
            ret['avg loop time'] = (float(loop_mem_entries[-1][1] -
                                    loop_mem_entries[0][1]) /
                                    loop_mem_entries[-1][0])

        # Maximum memory usage.
        ret['mxmem'] = max(entry[2] for entry in ret['memory'])

        # Startup time (time from running cmd to reaching the end of the first
        # loop).
        if not validate:
            ret['startup time'] = (loop_mem_entries[0][1] -
                                   round(float(suite_start_time), 1))

        # Awake CPU time.
        if not validate:
            ret['awake cpu time'] = (ret['cpu time'] - ret['sleep time'])

    return ret


def process_results(results):
    """Average over results for each run."""
    processed_results = {}
    all_metrics = set(METRICS.keys())
    for run_name, run in results.items():
        processed_results[run_name] = {}
        this_result = dict((metric, []) for metric in all_metrics)
        for result in run:
            for metric in all_metrics:
                for field in METRICS[metric][METRIC_FIELDS]:
                    if field in result:
                        this_result[metric].append(result[field])
            all_metrics = all_metrics & set(this_result.keys())
        for metric in all_metrics:
            if this_result[metric]:
                processed_results[run_name][metric] = mean(this_result[metric])
    for metric in set(METRICS.keys()) - all_metrics:
        for run_name, run in processed_results.items():
            del run[metric]
    return processed_results


def get_metrics_for_experiment(experiment, results, quick_analysis=False):
    """Return a set of metric keys present in the results for experiment

    If a metric is missing from one result it is skipped.

    """
    metrics = set([])
    for version_id in results:
        if experiment['id'] in results[version_id]:
            for run in results[version_id][experiment['id']].values():
                if metrics:
                    metrics = metrics & set(run.keys())
                else:
                    metrics = set(run.keys())
    if quick_analysis:
        return metrics & QUICK_ANALYSIS_METRICS
    return metrics


def get_metric_title(metric):
    """Return a user-presentable title for a given metric key."""
    metric_title = METRICS[metric][METRIC_TITLE]
    metric_unit = METRICS[metric][METRIC_UNIT]
    if metric_unit:
        metric_title += ' (' + metric_unit + ')'
    return metric_title


def make_table(results, versions, experiment, quick_analysis=False):
    """Produce a 2D array representing the results of the provided
    experiment."""
    metrics = get_metrics_for_experiment(experiment, results,
                                         quick_analysis=quick_analysis)

    # Make header rows.
    table = [['Version', 'Run'] + [get_metric_title(metric) for metric in
                                   sorted(metrics)]]

    # Make content rows.
    try:
        for version in versions:
            data = results[version['id']][experiment['id']]
            run_names = list(data)
            try:
                run_names.sort(key=int)
            except ValueError:
                run_names.sort()
            for run_name in run_names:
                table.append([version['name'], run_name] +
                             [data[run_name][metric] for metric in
                              sorted(metrics)])
    except ValueError:
        print('ERROR: Data is not complete. Try removing results and '
              're-running any experiments')

    return table


def print_table(table, transpose=False):
    """Print a 2D list as a table.

    None values are printed as hyphens, use '' for blank cells.
    """
    if transpose:
        table = list(map(list, list(zip(*table))))
    if not table:
        return
    for row_no, _ in enumerate(table):
        for col_no, _ in enumerate(table[0]):
            cell = table[row_no][col_no]
            if cell is None:
                table[row_no][col_no] = []
            else:
                table[row_no][col_no] = str(cell)

    col_widths = []
    for col_no, _ in enumerate(table[0]):
        col_widths.append(
            max(len(table[row_no][col_no]) for row_no, _ in enumerate(table)))

    for row_no, _ in enumerate(table):
        for col_no, _ in enumerate(table[row_no]):
            if col_no != 0:
                sys.stdout.write('  ')
            cell = table[row_no][col_no]
            if isinstance(cell, list):
                sys.stdout.write('-' * col_widths[col_no])
            else:
                sys.stdout.write(cell + ' ' * (col_widths[col_no] - len(cell)))
        sys.stdout.write('\n')


def plot_single(results, run_names, versions, metric, experiment,
                axis, c_map):
    """Create a bar chart comparing the results of all runs."""
    n_groups = len(versions)
    n_bars = len(run_names)
    ind = numpy.arange(n_groups)
    spacing = 0.1
    width = (1. - spacing) / n_bars
    colours = [c_map(x / (n_bars - 0.99)) for x in range(n_bars)]

    for bar_no, run_name in enumerate(run_names):
        data = [results[version['id']][experiment['id']][run_name][metric]
                for version in versions]
        axis.bar(ind + (bar_no * width), data, width, label=run_name,
                 color=colours[bar_no])

    axis.set_xticks(ind + ((width * n_bars) / 2.))
    axis.set_xticklabels([version['name'] for version in versions])
    axis.set_xlabel('Cylc Version')
    axis.set_xlim([0, (1. * n_groups) - spacing])
    if len(run_names) > 1:
        axis.legend(loc='upper left', prop={'size': 9})


def plot_scale(results, run_names, versions, metric, experiment,
               axis, c_map, lobf_order=2):
    """Create a scatter plot with line of best fit interpreting float(run_name)
    as the x-axis value."""
    x_data = [int(run_name) for run_name in run_names]
    colours = [c_map(x / (len(versions) - 0.99))
               for x, _ in enumerate(versions)]

    for ver_no, version in enumerate(reversed(versions)):
        y_data = []
        for run_name in run_names:
            y_data.append(
                results[version['id']][experiment['id']][run_name][metric]
            )

        # Plot data point.
        if lobf_order >= 1:
            axis.plot(x_data, y_data, 'x', color=colours[ver_no])
        else:
            axis.plot(x_data, y_data, 'x', color=colours[ver_no],
                      label=version['name'])

        # Compute and plot line of best fit.
        if lobf_order >= 1:
            if lobf_order > 8:
                print(('WARNING: Line of best fit order too high (' +
                      lobf_order + '). Order has been set to 3.'))
                lobf_order = 3
            lobf = numpy.polyfit(x_data, y_data, lobf_order)
            line = numpy.linspace(x_data[0], x_data[-1], 100)
            points = numpy.poly1d(lobf)(line)
            axis.plot(line, points, '-', color=colours[ver_no],
                      label=version['name'])

        # Plot settings.
        axis.set_xlabel(experiment['config']['x-axis'] if 'x-axis' in
                        experiment['config'] else 'Tasks')
        axis.legend(loc='upper left', prop={'size': 9})


def plot_results(results, versions, experiment, plt_dir=None,
                 quick_analysis=False, lobf_order=2):
    """Plot the results for the provided experiment.

    By default plots are
    written out to plt_dir. If not plt_dir then the plots will be displayed
    interactively.

    Args:
        results (dict): The data contained in the profiling results file.
        versions (list): List of version dictionaries for versions to plot.
        experiment (dict): Experiment dict for the experiment to plot.
        plt_dir (str): Directory to render any plots into.
        quick_analysis (bool - optional): If True only a small set of metrics
            will be plotted.
        lobf_order (int - optional): The polynomial order for the line of best
            fit, will be used for ALL plots.

    """
    # Are we able to plot?
    if not CAN_PLOT:
        print('\nWarning: Plotting requires numpy and maplotlib so cannot be '
              'run.')
        return

    versions = remove_profile_from_versions(versions)

    metrics = get_metrics_for_experiment(experiment, results,
                                         quick_analysis=quick_analysis)
    run_names = [run['name'] for run in experiment['config']['runs']]
    plot_type = experiment['config']['analysis']

    c_map = colour_map.Set1

    # One plot per metric.
    for metric in metrics:
        # Set up plotting.
        fig = plt.figure(111)
        axis = fig.add_subplot(111)

        if plot_type == 'single':
            plot_single(results, run_names, versions, metric,
                        experiment, axis, c_map)
        elif plot_type == 'scale':
            plot_scale(results, run_names, versions, metric,
                       experiment, axis, c_map, lobf_order=lobf_order)

        # Common config.
        axis.grid(True)
        axis.set_ylabel(get_metric_title(metric))

        # Output graph.
        if not plt_dir:
            # Output directory not specified, use interactive mode.
            plt.show()
        else:
            # Output directory specified, save figure as a pdf.
            fig.savefig(os.path.join(plt_dir,
                                     METRICS[metric][METRIC_FILENAME] +
                                     '.pdf'))

            fig.clear()
