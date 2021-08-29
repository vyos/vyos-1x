<!-- include start from interface/mtu-68-1500.xml.i -->
<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>u32:68-1500</format>
      <description>Maximum Transmission Unit in byte</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 68-1500"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 68 and 1500</constraintErrorMessage>
  </properties>
  <defaultValue>1500</defaultValue>
</leafNode>
<!-- include end -->
