<!-- include start from monitoring/blackbox-module-commons.xml.i -->
<leafNode name="timeout">
  <properties>
    <help>Timeout in seconds for the probe request</help>
    <valueHelp>
      <format>u32:1-60</format>
      <description>Timeout in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-60"/>
    </constraint>
    <constraintErrorMessage>Timeout must be between 1 and 60 seconds</constraintErrorMessage>
  </properties>
  <defaultValue>5</defaultValue>
</leafNode>
<leafNode name="preferred-ip-protocol">
  <properties>
    <help>Preferred IP protocol for this module</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Prefer IPv4</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Prefer IPv6</description>
    </valueHelp>
    <constraint>
      <regex>(ipv4|ipv6)</regex>
    </constraint>
  </properties>
  <defaultValue>ip6</defaultValue>
</leafNode>
<leafNode name="ip-protocol-fallback">
  <properties>
    <help>Allow fallback to other IP protocol if necessary</help>
    <valueless/>
  </properties>
</leafNode>
<!-- include end -->