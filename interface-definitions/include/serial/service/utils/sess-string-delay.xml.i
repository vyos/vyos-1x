<!-- include start from serial/service/utils/sess-string-delay.xml.i -->
<leafNode name="session-string-delay">
  <properties>
    <help>Session Strings Delay after sending string</help>
    <valueHelp>
      <format>u32:0-65535</format>
      <description>Specifies the delay in milliseconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-65535"/>
    </constraint>
  </properties>
  <defaultValue>0</defaultValue>
</leafNode>
<!-- include end -->
