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

import sys
import os
from cylc.flow import __version__ as CYLC_VERSION


# -- General configuration ------------------------------------------------

# minimal Sphinx version required.
needs_sphinx = '1.5.3'

# Sphinx extension module names.
sys.path.append(os.path.abspath('custom'))  # path to custom extensions.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'cylc_lang',
]

# Add any paths that contain templates.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'The Cylc Suite Engine'
copyright = '2008-2019 NIWA & British Crown (Met Office) & Contributors'

# Versioning information. Sphinx advises version strictly meaning X.Y.
version = '.'.join(CYLC_VERSION.split('.')[:2])  # The short X.Y version.
release = CYLC_VERSION  # The full version, including alpha/beta/rc tags.

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'manni'

# Enable automatic numbering of any captioned figures, tables & code blocks.
numfig = True
numfig_secnum_depth = 0


# -- Options for HTML output ----------------------------------------------

# The builtin HTML theme to build upon, with customisations to it. Notably
# customise with a white 'sticky' sidebar; make headings & links text the Cylc
# logo colours & make code block background the logo green made much lighter.
html_theme = "classic"
html_theme_options = {
    "stickysidebar": True,
    "sidebarwidth": 250,
    "relbarbgcolor": "black",
    "footerbgcolor": "white",  # single-page HTML flashes this colour on scroll
    "footertextcolor": "black",
    "sidebarbgcolor": "white",
    "sidebartextcolor": "black",
    "sidebarlinkcolor": "#0000EE;",
    "headbgcolor": "white",
    "headtextcolor": "#FF5966",
    "linkcolor": "#0000EE;",
    "visitedlinkcolor": "#551A8B;",
    "headlinkcolor": "#0000EE;",
    "codebgcolor": "#ebf9f6",
}

# Custom sidebar templates, maps document names to template names.
html_sidebars = {
    '**': ['globaltoc.html', 'searchbox.html', 'sourcelink.html'],
    'using/windows': ['windowssidebar.html', 'searchbox.html'],
}

# Logo and favicon to display.
html_logo = "graphics/png/orig/cylc-logo.png"
# sphinx specifies this should be .ico format
html_favicon = "graphics/cylc-favicon.ico"

# Disable timestamp otherwise inserted at bottom of every page.
html_last_updated_fmt = ''

# Remove "Created using Sphinx" text in footer.
html_show_sphinx = False

# Output file base name for HTML help builder.
htmlhelp_basename = 'cylcdoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '11pt',
}

# Title for the cylc documentation section
CYLC_DOC_TITLE = 'Cylc Documentation'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    ('index', 'cylc.tex', CYLC_DOC_TITLE, copyright, 'manual'),
]

# Image file to place at the top of the title page.
latex_logo = "graphics/png/orig/cylc-logo.png"

# If true, show URL addresses after external links.
latex_show_urls = "footnote"


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'cylc', CYLC_DOC_TITLE, copyright, 1),
]

# If true, show URL addresses after external links.
man_show_urls = True


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    ('index', 'cylc', CYLC_DOC_TITLE, copyright, 'cylc', project,
     'Miscellaneous'),
]

# How to display URL addresses.
texinfo_show_urls = 'footnote'
