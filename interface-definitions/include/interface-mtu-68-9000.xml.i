<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>68-9000</format>
      <description>Maximum Transmission Unit</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 68-9000"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 68 and 9000</constraintErrorMessage>
  </properties>
</leafNode>
