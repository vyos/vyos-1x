<!-- include start from interface/mtu-68-16000.xml.i -->
<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>u32:68-16000</format>
      <description>Maximum Transmission Unit in byte</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 68-16000"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 68 and 16000</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
