<!-- include start from kernel-interface-tun.xml.i -->
<leafNode name="kernel-interface">
  <properties>
    <help>Kernel interface name</help>
    <valueHelp>
      <format>vpptunN</format>
      <description>Kernel interface name</description>
    </valueHelp>
    <constraint>
      <regex>vpptun\d+</regex>
    </constraint>
    <constraintErrorMessage>Kernel interface must start with vpptunN</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
