<!-- include start from interface/parameters-df.xml.i -->
<leafNode name="df">
  <properties>
    <help>Usage of the DF (don't Fragment) bit in outgoing packets</help>
    <completionHelp>
      <list>set unset inherit</list>
    </completionHelp>
    <valueHelp>
      <format>set</format>
      <description>Always set DF (don't fragment) bit</description>
    </valueHelp>
    <valueHelp>
      <format>unset</format>
      <description>Always unset DF (don't fragment) bit</description>
    </valueHelp>
    <valueHelp>
      <format>inherit</format>
      <description>Copy from the original IP header</description>
    </valueHelp>
    <constraint>
      <regex>(set|unset|inherit)</regex>
    </constraint>
  </properties>
  <defaultValue>unset</defaultValue>
</leafNode>
<!-- include end -->
