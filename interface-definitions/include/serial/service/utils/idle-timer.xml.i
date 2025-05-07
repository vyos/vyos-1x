<!-- include start from serial/service/utils/idle-timer.xml.i -->
<leafNode name="idle-timer">
  <properties>
    <help>Close a connection because of inactivity when the Idle Timeout expires (in s, default: 0)</help>
    <valueHelp>
      <format>u32:0-4294967</format>
      <description>Decimal integer (0 - 4294967)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
