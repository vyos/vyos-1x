<!-- include start from serial/service/utils/session-timeout.xml.i -->
<leafNode name="session-timeout">
  <properties>
    <help>Close the session/connection when the Session Timeout expires (in s)</help>
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
