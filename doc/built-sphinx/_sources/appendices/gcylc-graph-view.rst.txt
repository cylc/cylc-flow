.. _TheGraphBasedcontrolGUI:

The gcylc Graph View
====================

The graph view in the gcylc GUI shows the structure of the suite as it
evolves. It can work well even for large suites, but be aware that the
Graphviz layout engine has to do a new global layout every time a task
proxy appears in or disappears from the task pool. The following may help
mitigate any jumping layout problems:

- The disconnect button can be used to temporarily prevent the
  graph from changing as the suite evolves.
- The greyed-out base nodes, which are only present to fill out
  the graph structure, can be toggled off (but this will split the
  graph into disconnected sub-trees).
- Right-click on a task and choose the "Focus" option to restrict
  the graph display to that task's cycle point. Anything interesting
  happening in other cycle points will show up as disconnected
  rectangular nodes to the right of the graph (and you can click on
  those to instantly refocus to their cycle points).
- Task filtering is the ultimate quick route to focusing on just
  the tasks you're interested in, but this will destroy the graph
  structure.


.. only:: builder_html

   .. include:: ../custom/whitespace_include
