<!-- include start from serial/general/remap-util.xml.i -->
<leafNode name="remap">
  <properties>
    <help>Actual baud rate (baud rate on the serial port)</help>
    <valueHelp>
      <format>u32:300-1843200</format>
      <description>Decimal integer (300 - 1843200)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 300-1843200"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
