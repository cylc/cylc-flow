Using Data To Define Your Workflow
==================================

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/external-data-files

We often want to read in a dataset for use in defining our workflow.

The :ref:`Cylc tutorial <tutorial-cylc-consolidating-configuration>` is an
example of this where we want one ``get_observations`` task for each of a list
of weather stations. Each weather station has a name (e.g. "heathrow") and an
ID (e.g. 3772).

.. code-block:: cylc

   [runtime]
       [[get_observations_heathrow]]
           script = get-observations
           [[[environment]]]
               SITE_ID = 3772
       [[get_observations_camborne]]
           script = get-observations
           [[[environment]]]
               SITE_ID = 3808
       [[get_observations_shetland]]
           script = get-observations
           [[[environment]]]
               SITE_ID = 3005
       [[get_observations_aldergrove]]
           script = get-observations
           [[[environment]]]
               SITE_ID = 3917

It can be inconvenient to write out the name and ID of each station in your
workflow like this, however, you may already have this information in a more
convenient format (i.e. a data file of some form).

With Cylc, we can use :ref:`Jinja2 <Jinja>` to read in a data file and use that data to
define your workflow.


The Approach
------------

This example has three components:

1. A JSON file containing a list of weather stations along with all the data
   associated with them.

   .. literalinclude:: stations.json
      :language: json
      :caption: stations.json

2. A Python function that reads the JSON file.

   .. code-block:: python
      :caption: lib/python/load_data.py
   
      import json
      
      
      def load_json(filename):
          with open(filename, 'r') as json_file:
              return json.load(json_file)

   We put this Python code in the workflow's ``lib/python`` directory which
   allows us to import it from within our workflow.

3. A ``flow.cylc`` file that uses the Python function to load the
   data file.

   We can import Python functions with Jinja2 using the following syntax:

   .. code-block::

      {% from "load_data" import load_json %}

   For more information, see :ref:`jinja2.importing_python_modules`.



The Workflow
------------

The three files are arranged like so:

.. code-block:: none
   :caption: File Structure

   |-- flow.cylc
   |-- lib
   |   `-- python
   |       `-- load_data.py
   `-- stations.json

The ``flow.cylc`` file:

* Imports the Python function.
* Uses it to load the data.
* Then uses the data to define the workflow.

.. literalinclude:: flow.cylc
   :language: ini
   :caption: flow.cylc


Data Types
----------

We can load other types of data file too. This example also includes the same
data in CSV format along with a Python function to load CSV data. To try it
out, open the ``flow.cylc`` file and replace ``stations.json`` with
``stations.csv`` and ``load_json`` with ``load_csv``.

Any Python code that you import using Jinja2 will be executed using the Python
environment that Cylc is running in. So if you want to import Python code that
isn't in the standard library, you may need to get your system administrator to
install this dependency into the Cylc environment for you.
