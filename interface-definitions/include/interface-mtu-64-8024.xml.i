<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <valueHelp>
      <format>64-8024</format>
      <description>Maximum Transmission Unit</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 64-8024"/>
    </constraint>
    <constraintErrorMessage>MTU must be between 64 and 8024</constraintErrorMessage>
  </properties>
</leafNode>
