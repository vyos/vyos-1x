<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>1200-9000</format>
      <description>Maximum Transmission Unit</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1200-9000"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 1200 and 9000</constraintErrorMessage>
  </properties>
  <defaultValue>1500</defaultValue>
</leafNode>
