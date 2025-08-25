<!-- include start from vpp/acl_prefix.xml.i -->
<leafNode name="prefix">
  <properties>
    <help>IP prefix</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 prefix</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6net</format>
      <description>IPv6 prefix</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
      <validator name="ipv6-prefix"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->

