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
        
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "log viewer" )

        combobox = gtk.combo_box_new_text()
        combobox.append_text( 'Filter' ) 
        combobox.append_text( 'all' ) 
        for task in self.task_list:
            combobox.append_text( task )

        combobox.connect("changed", self.filter_log )
        combobox.set_active(0)

        self.hbox.pack_end( combobox, False )

        newer = gtk.Button( "_newer" )
        newer.connect("clicked", self.rotate_log, False )
        self.hbox.pack_end( newer, False )

        older = gtk.Button( "_older" )
        older.connect("clicked", self.rotate_log, True )
        self.hbox.pack_end( older, False )

        filterbox = gtk.HBox()
        entry = gtk.Entry()
        entry.connect( "activate", self.custom_filter_log )
        label = gtk.Label('Filter')
        filterbox.pack_start(label, True)
        filterbox.pack_start(entry, True)
        self.hbox.pack_end( filterbox, False )

        close = gtk.Button( "_Close" )
        close.connect("clicked", self.shutdown, None, window )
        self.hbox.pack_end( close, False )

        window.add( self.vbox )
        window.connect("delete_event", self.shutdown, window )
 
        window.show_all()

    def shutdown( self, w, e, wind ):
        self.quit()
        wind.destroy()

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
        if go_older:
            self.level += 1
        else:
            self.level -= 1
        if self.level < 0:
            warning_dialog( """
At newest rotation; reloading in case 
the suite has been restarted.""" ).warn()
            self.level = 0
            # but update view in case user started suite after gui
        if self.current_log() not in os.listdir( self.dir ):
            if go_older:
                warning_dialog( "Older log not available" ).warn()
                self.level -= 1
                return
            else:
                warning_dialog( "Newer log not available" ).warn()
                self.level += 1
                return
        else:
            self.file = self.current_log()
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


