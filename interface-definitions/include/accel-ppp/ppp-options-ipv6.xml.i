<!-- include start from accel-ppp/ppp-options-ipv6.xml.i -->
<leafNode name="ipv6">
  <properties>
    <help>IPv6 (IPCP6) negotiation algorithm</help>
    <constraint>
      <regex>(deny|allow|prefer|require)</regex>
    </constraint>
    <constraintErrorMessage>invalid value</constraintErrorMessage>
    <valueHelp>
      <format>deny</format>
      <description>Do not negotiate IPv6</description>
    </valueHelp>
    <valueHelp>
      <format>allow</format>
      <description>Negotiate IPv6 only if client requests</description>
    </valueHelp>
    <valueHelp>
      <format>prefer</format>
      <description>Ask client for IPv6 negotiation, do not fail if it rejects</description>
    </valueHelp>
    <valueHelp>
      <format>require</format>
      <description>Require IPv6 negotiation</description>
    </valueHelp>
    <completionHelp>
      <list>deny allow prefer require</list>
    </completionHelp>
  </properties>
  <defaultValue>deny</defaultValue>
</leafNode>
<!-- include end -->
