<!-- include start from bgp/neigbhor-local-role.xml.i -->
<tagNode name="local-role">
  <properties>
    <help>Local role for BGP neighbor (RFC9234)</help>
    <completionHelp>
      <list>customer peer provider rs-client rs-server</list>
    </completionHelp>
    <valueHelp>
      <format>customer</format>
      <description>Using Transit</description>
    </valueHelp>
    <valueHelp>
      <format>peer</format>
      <description>Public/Private Peering</description>
    </valueHelp>
    <valueHelp>
      <format>provider</format>
      <description>Providing Transit</description>
    </valueHelp>
    <valueHelp>
      <format>rs-client</format>
      <description>RS Client</description>
    </valueHelp>
    <valueHelp>
      <format>rs-server</format>
      <description>Route Server</description>
    </valueHelp>
    <constraint>
      <regex>(provider|rs-server|rs-client|customer|peer)</regex>
    </constraint>
    <constraintErrorMessage>BGP local-role must be one of the following: customer, peer, provider, rs-client or rs-server</constraintErrorMessage>
  </properties>
  <children>
    <leafNode name="strict">
      <properties>
        <help>Neighbor must send this exact capability, otherwise a role missmatch notification will be sent</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
