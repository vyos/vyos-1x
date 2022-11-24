<!-- include start from firewall/add-dynamic-ipv6-address-groups.xml.i -->
<leafNode name="address-group">
  <properties>
    <help>Dynamic ipv6-address-group</help>
    <completionHelp>
      <path>firewall dynamic-group ipv6-address-group</path>
    </completionHelp>
  </properties>
</leafNode>
<leafNode name="timeout-value">
  <properties>
    <help>Set timeout</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Remains element in group for this time</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="timeout-unit">
  <properties>
    <help>Timeout unit: second/minute/hour/day</help>
    <completionHelp>
      <list>second minute hour day</list>
    </completionHelp>
    <valueHelp>
      <format>second</format>
      <description>Second</description>
    </valueHelp>
    <valueHelp>
      <format>minute</format>
      <description>Minute</description>
    </valueHelp>
    <valueHelp>
      <format>hour</format>
      <description>Hour</description>
    </valueHelp>
    <valueHelp>
      <format>day</format>
      <description>Day</description>
    </valueHelp>
    <constraint>
      <regex>(second|minute|hour|day)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
