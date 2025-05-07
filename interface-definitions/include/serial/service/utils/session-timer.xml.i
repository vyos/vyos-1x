<!-- include start from serial/service/utils/session-timer.xml.i -->
<leafNode name="sess-timer">
  <properties>
    <help>Close the session/connection when the Session Timeout expires (in s, default: 0)</help>
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
