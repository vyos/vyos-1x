<!-- include start from snmp/privacy-type.xml.i -->
<leafNode name="type">
  <properties>
    <help>Defines the protocol for privacy</help>
    <completionHelp>
      <list>des aes</list>
    </completionHelp>
    <valueHelp>
      <format>des</format>
      <description>Data Encryption Standard</description>
    </valueHelp>
    <valueHelp>
      <format>aes</format>
      <description>Advanced Encryption Standard</description>
    </valueHelp>
    <constraint>
      <regex>(des|aes)</regex>
    </constraint>
  </properties>
  <defaultValue>des</defaultValue>
</leafNode>
<!-- include end -->
