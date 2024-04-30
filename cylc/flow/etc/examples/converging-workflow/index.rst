Converging Workflow
===================

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/converging-workflow

A workflow which runs a pattern of tasks over and over until a convergence
condition has been met.

* The ``increment`` task runs some kind of model or process which increments
  us toward the solution.
* The ``check_convergence`` task, checks if the convergence condition has been
  met.

.. literalinclude:: flow.cylc
   :language: cylc

Run it with::

   $ cylc vip converging-workflow

.. admonition:: Example - Genetic algorithms
   :class: hint

   .. _genetic algorithm: https://en.wikipedia.org/wiki/Genetic_algorithm
   
   An example of a converging workflow might be a `genetic algorithm`_, where you
   "breed" entities, then test their "fitness", and breed again, over and over
   until you end up with an entity which is able to satisfy the requirement.
   
   .. digraph:: Example
   
      random_seed -> breed -> test_fitness
      test_fitness -> breed
      test_fitness -> stop
