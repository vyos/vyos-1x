<!-- include start from firewall/firewall-mark.xml.i -->
<leafNode name="mark">
  <properties>
    <help>Firewall mark</help>
    <valueHelp>
      <format>u32:0-2147483647</format>
      <description>Firewall mark to match</description>
    </valueHelp>
    <valueHelp>
      <format>!u32:0-2147483647</format>
      <description>Inverted Firewall mark to match</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>Firewall mark range to match</description>
    </valueHelp>
    <valueHelp>
      <format>!&lt;start-end&gt;</format>
      <description>Firewall mark inverted range to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric-exclude" argument="--allow-range --range 0-2147483647"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->