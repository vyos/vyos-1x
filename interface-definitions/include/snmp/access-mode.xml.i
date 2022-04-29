<!-- include start from snmp/access-mode.xml.i -->
<leafNode name="mode">
  <properties>
    <help>Define access permission</help>
    <completionHelp>
      <list>ro rw</list>
    </completionHelp>
    <valueHelp>
      <format>ro</format>
      <description>Read-Only</description>
    </valueHelp>
    <valueHelp>
      <format>rw</format>
      <description>read write</description>
    </valueHelp>
    <constraint>
      <regex>(ro|rw)</regex>
    </constraint>
    <constraintErrorMessage>Authorization type must be either 'rw' or 'ro'</constraintErrorMessage>
  </properties>
  <defaultValue>ro</defaultValue>
</leafNode>
<!-- include end -->
