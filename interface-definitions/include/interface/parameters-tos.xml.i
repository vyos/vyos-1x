<!-- include start from interface/tunnel-parameters-tos.xml.i -->
<leafNode name="tos">
  <properties>
    <help>Specifies TOS value to use in outgoing packets</help>
    <valueHelp>
      <format>u32:0-99</format>
      <description>Type of Service (TOS)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-99"/>
    </constraint>
    <constraintErrorMessage>TOS must be between 0 and 99</constraintErrorMessage>
  </properties>
  <defaultValue>inherit</defaultValue>
</leafNode>
<!-- include end -->
