<!-- include start from firewall/add-dynamic-ipv6-address-groups.xml.i -->
<leafNode name="address-group">
  <properties>
    <help>Dynamic ipv6-address-group</help>
    <completionHelp>
      <path>firewall group dynamic-group ipv6-address-group</path>
    </completionHelp>
  </properties>
</leafNode>
<leafNode name="timeout">
  <properties>
    <help>Set timeout</help>
    <valueHelp>
      <format>&lt;number&gt;s</format>
      <description>Timeout value in seconds</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;m</format>
      <description>Timeout value in minutes</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;h</format>
      <description>Timeout value in hours</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;d</format>
      <description>Timeout value in days</description>
    </valueHelp>
    <constraint>
      <regex>\d+(s|m|h|d)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->