.. _task-scheduler:

##############
Task Scheduler
##############

The task scheduler allows you to execute tasks on a given schedule. It makes
use of UNIX cron_.

.. note:: All scripts executed this way are executed as root user - this may
   be dangerous. Together with :ref:`command-scripting` this can be used for
   automating (re-)configuration.

.. cfgcmd:: set system task-scheduler task <task> interval <interval>

   Specify the time interval when `<task>` should be executed. The interval
   is specified as number with one of the following suffixes:

   * ``none`` - Execution interval in minutes
   * ``m`` - Execution interval in minutes
   * ``h`` - Execution interval in hours
   * ``d`` - Execution interval in days

   .. note:: If suffix is omitted, minutes are implied.

.. cfgcmd:: set system task-scheduler task <task> crontab-spec <spec>

   Set execution time in common cron_ time format. A cron `<spec>` of
   ``30 */6 * * *`` would execute the `<task>` at minute 30 past every 6th hour.

.. cfgcmd:: set system task-scheduler task <task> executable path <path>

   Specify absolute `<path>` to script which will be run when `<task>` is
   executed.

.. cfgcmd:: set system task-scheduler task <task> executable arguments <args>

   Arguments which will be passed to the executable.

.. _cron: https://en.wikipedia.org/wiki/Cron
