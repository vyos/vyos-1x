<!-- include start from haproxy/logging.xml.i -->
<node name="logging">
  <properties>
    <help>Logging parameters</help>
  </properties>
  <children>
    <tagNode name="facility">
      <properties>
        <help>Facility for logging</help>
        <completionHelp>
          <list>auth cron daemon kern lpr mail news syslog user uucp local0 local1 local2 local3 local4 local5 local6 local7</list>
        </completionHelp>
        <constraint>
          <regex>(auth|cron|daemon|kern|lpr|mail|news|syslog|user|uucp|local0|local1|local2|local3|local4|local5|local6|local7)</regex>
        </constraint>
        <constraintErrorMessage>Invalid facility type</constraintErrorMessage>
        <valueHelp>
          <format>auth</format>
          <description>Authentication and authorization</description>
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
              <list>emerg alert crit err warning notice info debug</list>
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
            <constraint>
              <regex>(emerg|alert|crit|err|warning|notice|info|debug)</regex>
            </constraint>
            <constraintErrorMessage>Invalid loglevel</constraintErrorMessage>
          </properties>
          <defaultValue>err</defaultValue>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
