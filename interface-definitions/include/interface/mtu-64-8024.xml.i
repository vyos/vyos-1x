<!-- include start from interface/mtu-68-8024.xml.i -->
<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>u32:64-8024</format>
      <description>Maximum Transmission Unit in byte</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 64-8024"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 64 and 8024</constraintErrorMessage>
  </properties>
  <defaultValue>1500</defaultValue>
</leafNode>
<!-- include end -->
