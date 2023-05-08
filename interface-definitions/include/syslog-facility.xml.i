<!-- include start from syslog-facility.xml.i -->
<tagNode name="facility">
  <properties>
    <help>Facility for logging</help>
    <completionHelp>
      <list>auth authpriv cron daemon kern lpr mail mark news syslog user uucp local0 local1 local2 local3 local4 local5 local6 local7 all</list>
    </completionHelp>
    <constraint>
      <regex>(auth|authpriv|cron|daemon|kern|lpr|mail|mark|news|syslog|user|uucp|local0|local1|local2|local3|local4|local5|local6|local7|all)</regex>
    </constraint>
    <constraintErrorMessage>Invalid facility type</constraintErrorMessage>
    <valueHelp>
      <format>all</format>
      <description>All facilities excluding "mark"</description>
    </valueHelp>
    <valueHelp>
      <format>auth</format>
      <description>Authentication and authorization</description>
    </valueHelp>
    <valueHelp>
      <format>authpriv</format>
      <description>Non-system authorization</description>
    </valueHelp>
    <valueHelp>
      <format>cron</format>
      <description>Cron daemon</description>
    </valueHelp>
    <valueHelp>
      <format>daemon</format>
      <description>System daemons</description>
    </valueHelp>
    <valueHelp>
      <format>kern</format>
      <description>Kernel</description>
    </valueHelp>
    <valueHelp>
      <format>lpr</format>
      <description>Line printer spooler</description>
    </valueHelp>
    <valueHelp>
      <format>mail</format>
      <description>Mail subsystem</description>
    </valueHelp>
    <valueHelp>
      <format>mark</format>
      <description>Timestamp</description>
    </valueHelp>
    <valueHelp>
      <format>news</format>
      <description>USENET subsystem</description>
    </valueHelp>
    <valueHelp>
      <format>syslog</format>
      <description>Authentication and authorization</description>
    </valueHelp>
    <valueHelp>
      <format>user</format>
      <description>Application processes</description>
    </valueHelp>
    <valueHelp>
      <format>uucp</format>
      <description>UUCP subsystem</description>
    </valueHelp>
    <valueHelp>
      <format>local0</format>
      <description>Local facility 0</description>
    </valueHelp>
    <valueHelp>
      <format>local1</format>
      <description>Local facility 1</description>
    </valueHelp>
    <valueHelp>
      <format>local2</format>
      <description>Local facility 2</description>
    </valueHelp>
    <valueHelp>
      <format>local3</format>
      <description>Local facility 3</description>
    </valueHelp>
    <valueHelp>
      <format>local4</format>
      <description>Local facility 4</description>
    </valueHelp>
    <valueHelp>
      <format>local5</format>
      <description>Local facility 5</description>
    </valueHelp>
    <valueHelp>
      <format>local6</format>
      <description>Local facility 6</description>
    </valueHelp>
    <valueHelp>
      <format>local7</format>
      <description>Local facility 7</description>
    </valueHelp>
  </properties>
  <children>
    <leafNode name="level">
      <properties>
        <help>Logging level</help>
        <completionHelp>
          <list>emerg alert crit err warning notice info debug all</list>
        </completionHelp>
        <valueHelp>
          <format>emerg</format>
          <description>Emergency messages</description>
        </valueHelp>
        <valueHelp>
          <format>alert</format>
          <description>Urgent messages</description>
        </valueHelp>
        <valueHelp>
          <format>crit</format>
          <description>Critical messages</description>
        </valueHelp>
        <valueHelp>
          <format>err</format>
          <description>Error messages</description>
        </valueHelp>
        <valueHelp>
          <format>warning</format>
          <description>Warning messages</description>
        </valueHelp>
        <valueHelp>
          <format>notice</format>
          <description>Messages for further investigation</description>
        </valueHelp>
        <valueHelp>
          <format>info</format>
          <description>Informational messages</description>
        </valueHelp>
        <valueHelp>
          <format>debug</format>
          <description>Debug messages</description>
        </valueHelp>
        <valueHelp>
          <format>all</format>
          <description>Log everything</description>
        </valueHelp>
        <constraint>
          <regex>(emerg|alert|crit|err|warning|notice|info|debug|all)</regex>
        </constraint>
        <constraintErrorMessage>Invalid loglevel</constraintErrorMessage>
      </properties>
      <defaultValue>err</defaultValue>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
