<!-- include start from interface/mtu-1450-16000.xml.i -->
<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>u32:1450-16000</format>
      <description>Maximum Transmission Unit in byte</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1450-16000"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 1450 and 16000</constraintErrorMessage>
  </properties>
  <defaultValue>1500</defaultValue>
</leafNode>
<!-- include end -->
