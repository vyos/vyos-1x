<!-- include start from firewall/connection-mark.xml.i -->
<leafNode name="connection-mark">
  <properties>
    <help>Connection mark</help>
    <valueHelp>
      <format>u32:0-2147483647</format>
      <description>Connection-mark to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-2147483647"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
