.. _event-handler:

#############
Event Handler
#############

*********************************
Event Handler Technology Overview
*********************************

Event handler allows you to execute scripts when a string that matches
a regex or a regex with a service name appears in journald logs. You
can pass variables, arguments, and a full matching string to the script.


******************************
How to configure Event Handler
******************************

    `1. Create an event handler`_

    `2. Add regex to the script`_

    `3. Add a full path to the script`_

    `4. Add optional parameters`_

*********************************
Event Handler Configuration Steps
*********************************

1. Create an event handler
==========================

    .. cfgcmd:: set service event-handler event <event-handler name>

    This is an optional command because the event handler will be
    automatically created after any of the next commands.


2. Add regex to the script
===========================================

.. stop_vyoslinter

    .. cfgcmd:: set service event-handler event <event-handler name> filter pattern <regex>

.. start_vyoslinter

    This is a mandatory command. Sets regular expression to match
    against log string message.

    .. note:: The regular expression matches if and only if the entire
       string matches the pattern.



3. Add a full path to the script
================================

.. stop_vyoslinter

    .. cfgcmd:: set service event-handler event <event-handler name> script path <path to script>

.. start_vyoslinter

    This is a mandatory command. Sets the full path to the script.
    The script file must be executable.


   
4. Add optional parameters
==========================

.. stop_vyoslinter

    .. cfgcmd:: set service event-handler event <event-handler name> filter syslog-identifier <syslogid name>

.. start_vyoslinter

    This is an optional command. Filters log messages by syslog-identifier.

.. stop_vyoslinter

    .. cfgcmd:: set service event-handler event <event-handler name> script environment <env name> value <env value>

.. start_vyoslinter

    This is an optional command. Adds environment and its value to the
    script. Use separate commands for each environment.
    
    One implicit environment exists.
    
    * ``message``: Full message that has triggered the script.

.. stop_vyoslinter

    .. cfgcmd:: set service event-handler event <event-handler name> script arguments <arguments>

.. start_vyoslinter

    This is an optional command. Adds arguments to the script.
    Arguments must be separated by spaces.

    .. note:: We don't recommend to use arguments. Using environments
       is more preferable.
    

*******
Example
*******

    Event handler that monitors the state of interface eth0.

.. stop_vyoslinter

    .. code-block:: none

      set service event-handler event INTERFACE_STATE_DOWN filter pattern '.*eth0.*,RUNNING,.*->.*'
      set service event-handler event INTERFACE_STATE_DOWN filter syslog-identifier 'netplugd'
      set service event-handler event INTERFACE_STATE_DOWN script environment interface_action value 'down'
      set service event-handler event INTERFACE_STATE_DOWN script environment interface_name value 'eth0'
      set service event-handler event INTERFACE_STATE_DOWN script path '/config/scripts/eventhandler.py'

    Event handler script

    .. code-block:: none

      #!/usr/bin/env python3
      #
      # VyOS event-handler script example
      from os import environ
      import subprocess
      from sys import exit

      # Perform actions according to requirements
      def process_event() -> None:
          # Get variables
          message_text = environ.get('message')
          interface_name = environ.get('interface_name')
          interface_action = environ.get('interface_action')
          # Print the message that triggered this script
          print(f'Logged message: {message_text}')
          # Prepare a command to run
          command = f'sudo ip link set {interface_name} {interface_action}'.split()
          # Execute a command
          subprocess.run(command)

      if __name__ == '__main__':
          try:
              # Run script actions and exit
              process_event()
              exit(0)
          except Exception as err:
              # Exit properly in case if something in the script goes wrong
              print(f'Error running script: {err}')
              exit(1)

.. start_vyoslinter
