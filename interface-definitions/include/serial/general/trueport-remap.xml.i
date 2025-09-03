<!-- include start from serial/service/general/trueport-remap.xml.i -->
<node name="trueport-baud">
  <properties>
    <help>Trueport baud rate remapping setting</help>
  </properties>
  <children>
    <tagNode name="speed">
      <properties>
        <help>Trueport baud rate (running on the application software)</help>
        <completionHelp>
          <list>50 75 110 134 150 200 300 600 1200 1800 2400 4800 9600 19200 38400</list>
        </completionHelp>
        <constraint>
          <regex>(50|75|110|134|150|200|300|600|1200|1800|2400|4800|9600|19200|38400)</regex>
        </constraint>
      </properties>
      <children>
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
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
