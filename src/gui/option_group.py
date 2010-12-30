#!/usr/bin/env python

import gtk

# TO DO: derive from option_group:

class controlled_option_group(object):
    def __init__( self, title, option=None ):
        self.title = title
        self.option = option
        self.entries = {}        # name -> ( entry, label, option )
        self.arg_entries = {}    # name -> ( entry, label )
        self.checkbutton = gtk.CheckButton( title )
        self.checkbutton.connect( "toggled", self.greyout )
        
    def greyout( self, data=None ):
        if self.checkbutton.get_active():
            for name in self.entries:
                (entry,label,option) = self.entries[name]
                entry.set_sensitive(True)
        else:
            for name in self.entries:
                (entry,label,option) = self.entries[name]
                entry.set_sensitive(False)

    def add_arg_entry( self, name, max_chars=None, default=None ):
        label = gtk.Label( name )
        entry = gtk.Entry()
        if max_chars:
            entry.set_max_length( max_chars )
        if default:
            entry.set_text( default )
        entry.set_sensitive( False )
        self.arg_entries[ name ] = ( entry, label )

    def add_entry( self, name, option, max_chars=None, default=None ):
        label = gtk.Label( name )
        entry = gtk.Entry()
        if max_chars:
            entry.set_max_length( max_chars )
        if default:
            entry.set_text( default )
        entry.set_sensitive( False )
        self.entries[ name ] = ( entry, label, option )

    def pack( self, vbox ):
        vbox.pack_start( self.checkbutton ) 
        for name in self.entries: 
            ( entry, label, option ) = self.entries[name]
            box = gtk.HBox()
            box.pack_start( label, True )
            box.pack_start( entry, True )
            vbox.pack_start( box )
        for name in self.arg_entries: 
            ( entry, label ) = self.entries[name]
            box = gtk.HBox()
            box.pack_start( label, True )
            box.pack_start( entry, True )
            vbox.pack_start( box )

    def get_options( self ):
        if not self.checkbutton.get_active():
            return ''
        if self.option:
            options = ' ' + self.option
        else:
            options = ' '
        for name in self.entries:
            (entry, label, option) = self.entries[name]
            if entry.get_text():
                options += ' ' + option + entry.get_text()
        for name in self.arg_entries:
            (entry, label) = self.arg_entries[name]
            if entry.get_text():
                options += ' ' + entry.get_text()
        return options


class option_group(object):
    def __init__( self ):
        self.entries = {}        # name -> ( entry, label, option )
        self.arg_entries = {}    # name -> ( entry, label )
        
    def add_arg_entry( self, name, max_chars=None, default=None ):
        label = gtk.Label( name )
        entry = gtk.Entry()
        if max_chars:
            entry.set_max_length( max_chars )
        if default:
            entry.set_text( default )
        self.arg_entries[ name ] = ( entry, label )

    def add_entry( self, name, option, max_chars=None, default=None ):
        label = gtk.Label( name )
        entry = gtk.Entry()
        if max_chars:
            entry.set_max_length( max_chars )
        if default:
            entry.set_text( default )
        self.entries[ name ] = ( entry, label, option )

    def pack( self, vbox ):
        for name in self.entries: 
            ( entry, label, option ) = self.entries[name]
            box = gtk.HBox()
            box.pack_start( label, True )
            box.pack_start( entry, True )
            vbox.pack_start( box )
        for name in self.arg_entries: 
            ( entry, label ) = self.arg_entries[name]
            box = gtk.HBox()
            box.pack_start( label, True )
            box.pack_start( entry, True )
            vbox.pack_start( box )

    def get_entries( self ):
        return self.entries + self.arg_entries

    def get_options( self ):
        options = ''
        for name in self.entries:
            (entry, label, option) = self.entries[name]
            if entry.get_text():
                options += ' ' + option + entry.get_text()
        for name in self.arg_entries:
            (entry, label) = self.arg_entries[name]
            if entry.get_text():
                options += ' ' + entry.get_text()
        return options
