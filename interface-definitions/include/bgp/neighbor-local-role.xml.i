<!-- include start from bgp/neigbhor-local-role.xml.i -->
<tagNode name="local-role">
  <properties>
    <help>Local role for this bgp session.</help>
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
    <constraintErrorMessage>Invalid Option</constraintErrorMessage>
  </properties>
  <children>
    <leafNode name="strict">
      <properties>
        <help>Your neighbor must send you Capability with the value of his role. Otherwise, a Role Mismatch Notification will be sent.</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
