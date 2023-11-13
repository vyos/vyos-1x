<!-- include start from pim/keep-alive-timer.xml.i -->
<leafNode name="keep-alive-timer">
  <properties>
    <help>Keep alive Timer</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Keep alive Timer in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
