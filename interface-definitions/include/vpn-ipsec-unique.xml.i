<!-- include start from vpn-ipsec-unique.xml.i -->
<leafNode name="unique">
  <properties>
    <help>Connection uniqueness enforcement policy</help>
    <completionHelp>
      <list>never keep replace</list>
    </completionHelp>
    <valueHelp>
      <format>never</format>
      <description>Never enforce connection uniqueness</description>
    </valueHelp>
    <valueHelp>
      <format>keep</format>
      <description>Reject new connection attempts if the same peer has an active connection</description>
    </valueHelp>
    <valueHelp>
      <format>replace</format>
      <description>Delete existing connections when a new connection is established for the same peer</description>
    </valueHelp>
    <constraint>
      <regex>(never|keep|replace)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
