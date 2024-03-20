<!-- include start from interface/vif.xml.i -->
<leafNode name="protocol">
  <properties>
    <help>Protocol used for service VLAN (default: 802.1ad)</help>
    <completionHelp>
      <list>802.1ad 802.1q</list>
    </completionHelp>
    <valueHelp>
      <format>802.1ad</format>
      <description>Provider Bridging (IEEE 802.1ad, Q-inQ), ethertype 0x88a8</description>
    </valueHelp>
    <valueHelp>
      <format>802.1q</format>
      <description>VLAN-tagged frame (IEEE 802.1q), ethertype 0x8100</description>
    </valueHelp>
    <constraint>
      <regex>(802.1q|802.1ad)</regex>
    </constraint>
    <constraintErrorMessage>Ethertype must be 802.1ad or 802.1q</constraintErrorMessage>
  </properties>
  <defaultValue>802.1ad</defaultValue>
</leafNode>
<!-- include end -->
