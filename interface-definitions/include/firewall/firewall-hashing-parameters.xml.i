<!-- include start from firewall/firewall-hashing-parameters.xml.i -->
<leafNode name="hash">
  <properties>
    <help>Define the parameters of the packet header to apply the hashing</help>
    <completionHelp>
      <list>source-address destination-address source-port destination-port random</list>
    </completionHelp>
    <valueHelp>
      <format>source-address</format>
      <description>Use source IP address for hashing</description>
    </valueHelp>
    <valueHelp>
      <format>destination-address</format>
      <description>Use destination IP address for hashing</description>
    </valueHelp>
    <valueHelp>
      <format>source-port</format>
      <description>Use source port for hashing</description>
    </valueHelp>
    <valueHelp>
      <format>destination-port</format>
      <description>Use destination port for hashing</description>
    </valueHelp>
    <valueHelp>
      <format>random</format>
      <description>Do not use information from ip header. Use random value.</description>
    </valueHelp>
    <constraint>
      <regex>(source-address|destination-address|source-port|destination-port|random)</regex>
    </constraint>
    <multi/>
  </properties>
  <defaultValue>random</defaultValue>
</leafNode>
<!-- include end -->