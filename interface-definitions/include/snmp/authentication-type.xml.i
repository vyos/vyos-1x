<!-- include start from snmp/authentication-type.xml.i -->
<leafNode name="type">
  <properties>
    <help>Define used protocol</help>
    <completionHelp>
      <list>md5 sha</list>
    </completionHelp>
    <valueHelp>
      <format>md5</format>
      <description>Message Digest 5</description>
    </valueHelp>
    <valueHelp>
      <format>sha</format>
      <description>Secure Hash Algorithm</description>
    </valueHelp>
    <constraint>
      <regex>(md5|sha)</regex>
    </constraint>
  </properties>
  <defaultValue>md5</defaultValue>
</leafNode>
<!-- include end -->
