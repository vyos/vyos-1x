<!-- include start from firewall/dscp.xml.i -->
<leafNode name="dscp">
  <properties>
    <help>DSCP value</help>
    <valueHelp>
      <format>u32:0-63</format>
      <description>DSCP value to match</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>DSCP range to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 0-63"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<leafNode name="dscp-exclude">
  <properties>
    <help>DSCP value not to match</help>
    <valueHelp>
      <format>u32:0-63</format>
      <description>DSCP value not to match</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>DSCP range not to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 0-63"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->