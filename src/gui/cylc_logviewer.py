from filtered_tailer import filtered_tailer
from tailer import tailer
import gtk
import pygtk
####pygtk.require('2.0')
import time, os, re, sys
from warning_dialog import warning_dialog

from logviewer import logviewer

class cylc_logviewer( logviewer ):
 
    def __init__( self, name, dir, task_list ):
        self.task_list = task_list
        self.main_log = 'log'
        self.level = 0
        self.filter = None
        logviewer.__init__( self, name, dir, self.main_log )

    def create_gui_panel( self ):
        logviewer.create_gui_panel( self )
        
        combobox = gtk.combo_box_new_text()
        combobox.append_text( 'Filter' ) 
        combobox.append_text( 'all' ) 
        for task in self.task_list:
            combobox.append_text( task )

        combobox.connect("changed", self.filter_log )
        combobox.set_active(0)

        self.hbox.pack_end( combobox, False )

        previous = gtk.Button( "newer rotation" )
        previous.connect("clicked", self.rotate_log, False )
        self.hbox.pack_end( previous, False )

        previous = gtk.Button( "older rotation" )
        previous.connect("clicked", self.rotate_log, True )
        self.hbox.pack_end( previous, False )

        filterbox = gtk.HBox()
        entry = gtk.Entry()
        entry.connect( "activate", self.custom_filter_log )
        label = gtk.Label('Custom Filter (hit Enter)')
        filterbox.pack_start(label, True)
        filterbox.pack_start(entry, True)
        self.hbox.pack_end( filterbox, False )

    def filter_log( self, cb ):
        model = cb.get_model()
        index = cb.get_active()
        if index == 0:
            return False

        task = model[index][0]
        if task == 'all':
            filter = None
        else:
            filter = '\\[' + task + '%\d{10}\\]'

        self.filter = filter
        self.update_view()

        # TO DO: CHECK ALL BOOLEAN RETURN VALUES THROUGHOUT THE GUI
        return False

    def custom_filter_log( self, e ):
        txt = e.get_text()
        if txt == '':
            filter = None
        else:
            filter = txt

        self.filter = filter
        self.update_view()

        return False

    def current_log( self ):
        if self.level == 0:
            return self.main_log
        else:
            return self.main_log + '.' + str( self.level )

    def rotate_log( self, bt, go_older ):
        level = self.level
        if go_older:
            level += 1
        else:
            level -= 1

        if level < 0:
            warning_dialog( "The active log is already displayed" ).warn()
            return

        if self.current_log() not in os.listdir( self.dir ):
            warning_dialog( "No log not available" ).warn()
            return

        self.level = level
        self.update_view()

    def update_view( self ):
        self.t.quit = True
        logbuffer = self.logview.get_buffer()
        s,e = logbuffer.get_bounds()
        self.reset_logbuffer()
        logbuffer.delete( s, e )
        self.log_label.set_text( self.path() ) 
        if self.filter:
            self.t = filtered_tailer( self.logview, self.path(), self.filter )
        else:
            self.t = tailer( self.logview, self.path() )
        ###print "Starting log viewer thread"
        self.t.start()


