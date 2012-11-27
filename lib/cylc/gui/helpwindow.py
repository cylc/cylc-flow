#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import gtk
import pango
import string
from color_rotator import rotator
from util import get_icon

class helpwindow_base( object ):
    def __init__( self, title, height=400 ):
        self.window = gtk.Window()
        self.window.set_title( title )

        self.window.set_size_request(600, int(height))
        
        self.window.set_icon( get_icon() )

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "_Close" )
        quit_button.connect("clicked", lambda x: self.window.destroy() )
        vbox.pack_start( sw )
        vbox.pack_start( quit_button, False )

        textview = gtk.TextView()
        textview.set_border_width(5)
        textview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#def" ))
        textview.set_editable( False )
        textview.set_wrap_mode( gtk.WRAP_WORD )
        sw.add( textview )
        self.window.add( vbox )
        self.tb = textview.get_buffer()

        self.tag_text = self.tb.create_tag( None, foreground = "#222" )
        self.tag_title = self.tb.create_tag( None, foreground = "#003" )
        self.tag_heading = self.tb.create_tag( None, foreground = "#008" )
        self.tag_subheading = self.tb.create_tag( None, foreground = "#00f" )
        self.tag_bold = self.tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        self.add_main_heading( title )
        quit_button.grab_focus()
         
    def add_main_heading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n' + text + '\n', self.tag_bold, self.tag_title )

    def add_heading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n' + text, self.tag_bold, self.tag_heading )
 
    def add_subheading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n    ' + text, self.tag_bold, self.tag_subheading )

    def add_text( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text + '\n', self.tag_text )
 
    def add_text_bold( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text, self.tag_text, self.tag_bold )

    def add_list_item( self, item ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n o ', self.tag_bold )
        self.tb.insert_with_tags( self.tb.get_end_iter(), item, self.tag_text )

    def show( self ):
        self.window.show_all()

class helpwindow( helpwindow_base ):
    def __init__( self, title, height, text ):
        helpwindow_base.__init__(self, title, height )
        self.parse( text )

    def parse( self, text ):
        def strip( line ):
            # strip '%' tags
            return re.sub( '%[\w\d]+ ', '', line )

        # pre-parse to concatenate paragraphs into a single string
        # because textbuffer inserts seem to add a newline that 
        # stop line wrapping from working properly...
        lines = []
        para = ''
        for line in string.split( text, '\n' ):
            if re.match( '^%', line ):
                # tag
                if para != '':
                    lines.append(para)
                    para = ''
                lines.append(line)
            elif re.match( '^\s*$', line ):
                # blank
                lines.append(line)
                if para != '':
                    lines.append(para)
                    para = ''
            else:
                para += ' ' + line
        if para != '':
            lines.append(para)

        for line in lines:
            if re.match( '^\s*$', line ):
                # blank line
                self.add_text( '' )
            elif re.match( '^%h1', line ):
                self.add_main_heading( strip(line) )
            elif re.match( '^%h2', line ):
                self.add_heading( strip(line) )
            elif re.match( '^%h3', line ):
                self.add_subheading( strip(line) )
            elif re.match( '^%b', line ):
                self.add_text_bold( strip(line ))
            elif re.match( '^%i', line ):
                self.add_list_item( strip(line ))
            else:
                self.add_text( line )

##########
def main( b ):
    help = helpwindow( "cylc db viewer Main Window Help", 500, """%h2 Overview

cylc db viewer displays your suite registration database. Using the menu
bar and right-click menu items you can register new suites; copy,
reregister, and unregister existing suites; start a suite control GUI to
run a dormant suite or to connect to one that is already running; or
edit, search, validate, and graph suite definitions.

%h2 Menu Bar

%h3 File > Register Existing Suite
Register an existing suite. This opens a file chooser dialog configured
to filter for cylc suite definition (suite.rc) files.

%h3 File > Create New Suite
Create a new suite, initially with an empty suite.rc file. This opens a
directory chooser dialog in which you can choose or create the new suite
definition directory.

%h3 File > Exit
Quits the db viewer application, but not any external programs you have
launched from the viewer (such as suite edit sessions or gcylc apps).

%h3 View > Filter
Change which suites are visible by searching on group and name match
patterns.

%h3 View > Expand
Expand the registration database treeview.

%h3 View > Collapse
Collapse the registration database treeview.

%h3 View > Refresh
Check the database for invalid registrations (e.g. due to manual
deletion of a suite definition directory) and update any suite
titles that have changed. Changes to the database (e.g. suites 
registered or unregistered) are automatically detected by the GUI, but
titles are normally only parsed from suite.rc files at registration
time - use refresh if you change a suite's title.

%h3 View > Reload
Reload the suite database from scratch.

%h3 Database > User
(Not currently used)

%h2 Right Click Menu Options

The Right-Click menu options available depend on whether you have
clicked on a running suite, a dormant suite, or a group of suites.  For
options relating to suite registration, registration groups are created
and deleted as required (you don't need to explicitly create group 'foo'
before registering a suite 'foo:bar', for example).

Most right-click menu items invoke cylc command line programs inside a
wrapper that captures subprocess stdout and stderr streams and displays
in a window that updates in real time. These output log windows can be
closed without affecting the associated subprocess, but you will lose
access to the output (except in the case of the stdout/stderr from cylc
itself for suites that are started from a suite control GUI - see below).

If you start a suite from the command line, what happens to cylc stdout
and stderr is of course entirely up to you (you may want to use
command line redirection and/or the posix nohup command).

%h3 Control -> Dot or Graph Control GUI

Launch a suite control GUI, with either the "dot" (LED) text treeview
interface, or the dependency graph interface, to start a suite running,
or to connect to a suite that is already running. 

If you start the suite from within the control GUI, or if you connect to
a suite that was started from a control GUI, the GUI subprocess output
window will show cylc stdout and stderr as redirected to the files
$HOME/.cylc/GROUP:NAME.(out|err). If you start a suite from the
command line, where cylc stdout and stderr goes is up to you (use 
output redirection and/or the posix nohup command, for instance).

%h3 Control -> Submit A Task

Submit a single task from the suite, exactly as it would be submitted by
the suite.

%h3 Preparation|Info -> Description

Print the suite description as parsed from the suite.rc file.

%h3 Preparation|Info -> Edit

Edit the suite.rc file, optionally inlined. See 'cylc edit --help'.

%h3 Preparation -> View

View a read-only copy of the suite.rc file, optionally inlined or 
pre-processed by Jinja2. See 'cylc view --help'.

%h3 Preparation|Info -> List

Print the suite's task list, or namespace hierarchy (tasks and families)
in tree form.

%h3 Preparation|Info -> Graph

Plot the suite dependency graph. The graph viewer updates in real time
as you edit the suite definition. See 'cylc graph --help'.

%h3 Preparation -> Search

Search for strings or regular expressions in the suite.rc file and,
optionally, in the suite bin directory. See 'cylc grep --help'.

%h3 Preparation -> Validate

Parse the suite.rc file and validate it against the suite.rc spec, 
then attempt to instantiate all suite task proxies, and report any
errors. See 'cylc validate --help'.

%h3 Information -> View Suite Log
This opens a searchable and filterable view of the suite log file that
records, timestamped, all important events as the suite runs.

%h3 Information -> View Suite Output
This opens a new view of the suite stdout and stderr files
$HOME/.cylc/NAME.(out|err) used when suites are started from
within cylc db viewer (if you start a suite from the command line,
however, what happens to its stdout and stderr end up is entirely up to
you). The suite remembers task output locations while the corresponding
task proxies still exist in the suite (this information is not stored in 
suite state dump files, however, so it will be lost for finished tasks
still in the suite, if you stop and restart the suite).

%h3 Information -> Dump Suite State (Running suites only)
Print the current state of each task in the suite. 
See 'cylc info dump --help'.

%h3 Database -> Copy
Copy an existing suite (or group of suites) and register it (or them)
for use. See 'cylc db copy --help'.

%h3 Database -> Alias
Create an alias (generally a short nickname) for an existing registered
suite. Referring to a suite via its alias is entirely equivalent to using
the full registered name.  See 'cylc db alias --help'.

%h3 Database -> Reregister
Reregister an existing suite (or group of suites) under a different
name. See 'cylc db register --help'.

%h3 Database -> Unregister
Delete the registration of a suite (or group of suites) and optionally 
delete its (or their) suite definition directory(s).  
See 'cylc db unregister --help'.""")
    help.show()

def filter( b ):
    help = helpwindow( "Filter Help", 300, """
Change suite visibility by filtering on group and/or name with
(Python-style) regular expressions (so, for example, the
wildcard is '.*' not '*' as in a shell glob expression).

Leaving a filter entry blank is equivalent to '.*' (i.e. match
anything).

Filter patterns have an implicit string start character ('^')
but no implicit string end character ('$'). Examples:

%i foo - matches 'foo' and 'foobar', but not 'barfoo'
%i foo$ - matches 'foo' only
%i .*foo$  - matches 'foo', 'barfoo', but not 'foobar'
%i (?i)foo - case-insensitive (matches 'foo', 'Food', 'FOOb',...)
%i (foo|bar) - match 'foo' or 'bar' followed by anything""")
    help.show()

def todo( b) :
    help = helpwindow( "Commands or command options not yet implemented in the GUI", 300, """
%h2 'cylc restart --no-release' option: don't release held tasks on restarting a suite.""")
    help.show()

def capture( b ):
    help = helpwindow( "Subprocess Capture Help", 200, """
This window captures stdout and stderr messages, in real time, from
subprocesses spawned by the GUI. You can close this window without
adversely affecting the subprocess itself, BUT [1] when the subprocess 
ends it will leave zombie entry in the system process table until you 
close the gui (however, these are not real processes and do not
use system resources) and [2] you will lose access to the output streams
(except in the case of suites started from from gcylc, in which case the
output goes to special files that can be accessed again).""")
    help.show()

def graph_viewer( b ):
    help = helpwindow( "Graph Viewer Help", 500, """The graph viewer plots suite dependency graphs parsed from the suite.rc
file. The viewer updates automatically when the suite.rc file is saved
during editing (however, the [visualization] -> 'collapsed families' item
only affects the initial plot, after which any manual changes to family
node grouping, using the viewer controls, take precedence).

%h2 Controls

%i Center the graph: left-click on a node.
%i Pan: left-drag.
%i Zoom: Tool bar, mouse-wheel, Ctrl-left-drag, Shift-left-drag (box zoom).
%i Best Fit and Normal Size: Tool bar.

%h3 Family Grouping, Toolbar:
%i "group" - group all families up to root.
%i "ungroup" - recursively ungroup all families.

%h3 Family Grouping, Right-click menu:
%i "group" - close this node's parent family.
%i "ungroup" - open this family node.
%i "recursive ungroup" - ungroup all families below this node.""")
    help.show()


#-----------------------------------------------------------------------
# TO DO: THE FOLLOWING HELP WINDOWS SHOULD BE REDONE IN FORMATTED STRING 
# FORM, AS ABOVE.

def update_tb( tb, line, tags = None ):
    if tags:
        tb.insert_with_tags( tb.get_end_iter(), line, *tags )
    else:
        tb.insert( tb.get_end_iter(), line )

def userguide( w ):
    window = gtk.Window()
    window.set_title( "gcylc Quick Guide" )
    window.set_size_request(600, 600)
    window.set_icon( get_icon() )

    sw = gtk.ScrolledWindow()
    sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

    vbox = gtk.VBox()
    quit_button = gtk.Button( "_Close" )
    quit_button.connect("clicked", lambda x: window.destroy() )
    vbox.pack_start( sw )
    vbox.pack_start( quit_button, False )

    textview = gtk.TextView()
    textview.set_border_width(5)
    textview.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#fff" ))
    textview.set_editable( False )
    sw.add( textview )
    window.add( vbox )
    tb = textview.get_buffer()

    textview.set_wrap_mode( gtk.WRAP_WORD )

    blue = tb.create_tag( None, foreground = "blue" )
    red = tb.create_tag( None, foreground = "darkgreen" )
    alert = tb.create_tag( None, foreground = "red" )
    bold = tb.create_tag( None, weight = pango.WEIGHT_BOLD )

    update_tb( tb, "gcylc Suite Control GUI Quick Guide", [bold, blue] )

    update_tb( tb, "\n\nReal time cylc suite control and monitoring. "
            "See also 'cylc help' on the command line." )

    update_tb( tb, "\n\ngcylc can display up to two of the following "
            "suite views at once: " )

    update_tb( tb, "dot ", [bold] )
    
    update_tb( tb, "(a quick visual overview ordered by cycle time), " )
    
    update_tb( tb, "text ", [bold] )

    update_tb( tb, "(with task message and timing information, and optional "
            "collapsible task families), ")

    update_tb( tb, "graph ", [bold] )
    
    update_tb( tb, " (showing the dependency structure of the suite, with "
            "collapsible task families)." )
    
    update_tb( tb, "\n\nDifferent task colors ", [bold] )
    
    update_tb( tb, "represent different task states of live task proxies in the suite. "
            "See 'gcylc --help' for how to select or define color palettes." )

    update_tb( tb, 
            "\n\nRight-click on tasks in any view for task control "
            "and interrogation options.", [bold] )


    update_tb( tb, "\n\nMenu: File > ", [bold, red] )
    update_tb( tb, "\n o Exit: ", [bold])
    update_tb( tb, "Exit the control GUI (does not shut the suite down).")

    update_tb( tb, "\n\nMenu: View > ", [bold, red] )
    update_tb( tb, "\n o Nudge Suite: ", [bold])

    update_tb( tb, "Invoke the cylc task processing loop when nothing else "
            "is happening, in order to update estimated completion times "
            "(which are not yet shown in the graph-base GUI) and the "
            "\"state last updated at\" time in the status bar." )

    update_tb( tb, "\n o View Suite Log: ", [bold])
    update_tb( tb, "View the cylc log for this suite, updating the view "
            "in real time if the suite is running." )

    update_tb( tb, "\n o View Suite Info: ", [bold])
    update_tb( tb, "View the suite's description and task list." )

    update_tb( tb, "\n o (Graph View) Time Range Focus ", [bold])
    update_tb( tb, "Restrict display to a specified range of cycle times.")

    update_tb( tb, "\n o (Graph View) Toggle Graph Key ", [bold])
    update_tb( tb, "Show or remove the dependency graph color key.")

    update_tb( tb, "\n o (Graph View) Toggle Crop Base Graph ", [bold])
    update_tb( tb, "This controls whether or not the suite base "
                "graph (off-white coloured nodes) is plotted for tasks "
                "that are not currently present in the suite. Not plotting "
                "them may result in several apparently disconnected "
                "graph sections, but plotting them may not be advantageous "
                "if there are tasks with widely separated cycle times "
                "present." )

    update_tb( tb, "\n o Toggle Task Names ", [bold])
    update_tb( tb, "Show or remove task names in the upper \"light panel\" display.")

    update_tb( tb, "\n o Toggle Auto-Expand Tree ", [bold])
    update_tb( tb, "If on, any cycle times containing submitted, running, or "
                "failed tasks will be automatically expanded whenever the suite "
                "state is updated.")

    update_tb( tb, 
            "\n\nGraph view controls: ", [bold, red] )

    update_tb( tb,  "Left-click to center the graph on a "
            "node; left-drag to pan; Zoom buttons, mouse-wheel, or "
            "ctrl-left-drag to zoom in and out, and shift-left-drag to "
            "zoom in on a box. "
            "Right-click on nodes for task control "
            "and interrogation options. ", [bold] )

    update_tb( tb, 
            "\n\nNOTE that the graph view may jump around as the suite evolves "
            "because the graphviz layout engine performs a new global optimization "
            "each time the graph is plotted. The 'DIS|REconnect' "
            "toggle button is provided to freeze the action temporarily. "
            "Time-zoom, family grouping, and task-filtering can also be used "
            "to focus on particular parts of a suite." )

    update_tb( tb, "\n\nMenu: Control > ", [bold, red] )
    update_tb( tb, "\n o Run Suite: ", [bold])
    update_tb( tb, "Cold Start, Warm Start, Raw Start, or Restart the suite.")
    update_tb( tb, "\n o Stop Suite: ", [bold])
    update_tb( tb, "Shut down the suite when all currently running tasks have finished "
            "or immediately (beware of orphaned tasks!), or after a all tasks have "
            "passed a given cycle time, or after a particular wall clock time, or "
            "after a particular task has finished." )
    update_tb( tb, "\n o Hold Suite (pause): ", [bold])
    update_tb( tb, "Refrain from submitting tasks that are ready to run.")
    update_tb( tb, "\n o Release Suite (unpause): ", [bold])
    update_tb( tb, "Resume submitting tasks that are ready to run.")
    update_tb( tb, "\n o Insert Task(s): ", [bold])
    update_tb( tb, "Insert a task or task group into a running suite." )
    update_tb( tb, "\n o Block Access: ", [bold])
    update_tb( tb, "Refuse to comply with subsequent intervention commands." )
    update_tb( tb, "\n o Unblock Access: ", [bold])
    update_tb( tb, "Comply with subsequent intervention commands." )
    update_tb( tb, "\n o Change Runahead Limit: ", [bold])
    update_tb( tb, "Change the suite's configured runahead limit at "
            "run time." )

    update_tb( tb, "\n\nRight-Click Task Popup Menu > ", [bold, red] )
            
    update_tb( tb, "\n o (Graph View) Focus On YYYYMMDDHH: ", [bold])
    update_tb( tb, "Restrict the graph to just the cycle time of this node (task)." )
 
    update_tb( tb, "\n o (Graph View) Focus On Range: ", [bold])
    update_tb( tb, "Restrict the graph to a specified range of cycle times." )

    update_tb( tb, "\n o (Graph View) Focus Reset: ", [bold])
    update_tb( tb, "Reset any cycle time focusing and show the whole graph." )
  
    update_tb( tb, "\n o View ", [bold])
    update_tb( tb, "\n     - stdout log: ", [bold])
    update_tb( tb, "View the task's standard output log" )
    update_tb( tb, "\n     - stderr log: ", [bold])
    update_tb( tb, "View the task's standard error log" )
    update_tb( tb, "\n     - job script: ", [bold])
    update_tb( tb, "View the script generated to run this task" )
    update_tb( tb, "\n     - prereqs & outputs: ", [bold])
    update_tb( tb, "View task description and the current state "
            "of its prerequisites and outputs.")
    update_tb( tb, "\n     - run 'cylc show': ", [bold])
    update_tb( tb, "Run the 'cylc show' command on this task.")
    update_tb( tb, "\n o Trigger: ", [bold])
    update_tb( tb, "Set a task's prerequisites satisfied "
            "and, for clock-triggered tasks, ignore the trigger time. "
            "This will cause the task to trigger immediately (NOTE: "
            "if the suite is held (paused) the task will trigger when "
            "the hold is released)." )
    update_tb( tb, "\n o Reset State: ", [bold])
    update_tb( tb, "\n     - 'ready': ", [bold])
    update_tb( tb, "Set a task's prerequisites satisfied."
            "This is equivalent to 'Trigger' for non clock-triggered "
            "tasks (NOTE: if the suite is held (paused) the task will "
            "trigger when the hold is released)." )
    update_tb( tb, "\n     - 'waiting': ", [bold])
    update_tb( tb, "Set all of a task's prerequisites unsatisfied." )
    update_tb( tb, "\n      - 'succeeded': ", [bold])
    update_tb( tb, "Set all of a task's outputs completed." )
    update_tb( tb, "\n      - 'failed': ", [bold])
    update_tb( tb, "Put the task in the 'failed' state." )

    update_tb( tb, "\n o Force Spawn: ", [bold])
    update_tb( tb, "Force the task to spawn a successor if it hasn't done so already." )

    update_tb( tb, "\n o Hold: ", [bold])
    update_tb( tb, "Put a task in the 'held' state; "
            "it won't run or spawn until released." )

    update_tb( tb, "\n o Release: ", [bold])
    update_tb( tb, "Release a task from the 'held' state "
            "so that it can run again as normal." )

    update_tb( tb, "\n o Remove after spawning: ", [bold])
    update_tb( tb, "Remove a task from the suite after forcing it to "
            "spawn a successor if it has not done so already." )
    update_tb( tb, "\n o Remove without spawning: ", [bold])
    update_tb( tb, "Remove a task from the suite even if it has not "
            "yet spawned a successor (in which case it will be removed "
            "permanently unless re-inserted)." )
    update_tb( tb, "\n o Remove Tree (Recursive Purge): ", [bold])
    update_tb( tb, "Remove a task from the suite, then remove any task "
            "that would depend on it, then remove any tasks that would depend on "
            "those tasks, and so on, through to a given stop cycle." )

    update_tb( tb, "\n o Add A Prerequisite: ", [bold])
    update_tb( tb, "Here you can add a new prerequisite to a task at "
            "run time. Example of use: make a task wait on a one off task "
            "that it does not normally depend on but which has been "
            "inserted into the suite to handle some unusual situation.")


    window.show_all()

