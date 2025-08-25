<!-- include start from kernel-interface-tap.xml.i -->
<leafNode name="kernel-interface">
  <properties>
    <help>Kernel interface name</help>
    <valueHelp>
      <format>vpptapN</format>
      <description>Kernel interface name</description>
    </valueHelp>
    <constraint>
      <regex>vpptap\d+</regex>
    </constraint>
    <constraintErrorMessage>Kernel interface must start with vpptapN</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
