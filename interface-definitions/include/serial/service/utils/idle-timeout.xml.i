<!-- include start from serial/service/utils/idle-timeout.xml.i -->
<leafNode name="idle-timeout">
  <properties>
    <help>Close a connection because of inactivity when the Idle Timeout expires (in s)</help>
    <valueHelp>
      <format>u32:0-4294967</format>
      <description>Decimal integer (0 - 4294967)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967"/>
    </constraint>
  </properties>
  <defaultValue>0</defaultValue>
</leafNode>
<!-- include end -->
