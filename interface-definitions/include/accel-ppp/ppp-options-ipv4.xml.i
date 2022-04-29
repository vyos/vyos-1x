<!-- include start from accel-ppp/ppp-options-ipv4.xml.i -->
<leafNode name="ipv4">
  <properties>
    <help>IPv4 negotiation algorithm</help>
    <constraint>
      <regex>(deny|allow)</regex>
    </constraint>
    <constraintErrorMessage>invalid value</constraintErrorMessage>
    <valueHelp>
      <format>deny</format>
      <description>Do not negotiate IPv4</description>
    </valueHelp>
    <valueHelp>
      <format>allow</format>
      <description>Negotiate IPv4 only if client requests</description>
    </valueHelp>
    <completionHelp>
      <list>deny allow</list>
    </completionHelp>
  </properties>
  <defaultValue>allow</defaultValue>
</leafNode>
<!-- include end -->
