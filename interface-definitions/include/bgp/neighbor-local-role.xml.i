<!-- include start from bgp/neigbhor-local-role.xml.i -->
<leafNode name="local-role">
  <properties>
    <help>Local role for neighbor</help>
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
</leafNode>
<leafNode name="local-role-strict">
  <properties>
    <help>Strict enforcement of local-role - role mismatch notification will be sent if unconfigured on peer</help>
    <valueless/>
  </properties>
</leafNode>
<!-- include end -->
