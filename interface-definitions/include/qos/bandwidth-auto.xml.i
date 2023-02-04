<!-- include start from qos/bandwidth-auto.xml.i -->
<leafNode name="bandwidth">
  <properties>
    <help>Available bandwidth for this policy</help>
    <completionHelp>
      <list>auto</list>
    </completionHelp>
    <valueHelp>
      <format>auto</format>
      <description>Bandwidth matches interface speed</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;</format>
      <description>Bits per second</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;bit</format>
      <description>Bits per second</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;kbit</format>
      <description>Kilobits per second</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;mbit</format>
      <description>Megabits per second</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;gbit</format>
      <description>Gigabits per second</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;tbit</format>
      <description>Terabits per second</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;number&gt;%%</format>
      <description>Percentage of interface link speed</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--positive"/>
      <regex>(auto|\d+(bit|kbit|mbit|gbit|tbit)?|(100|\d(\d)?)%)</regex>
    </constraint>
  </properties>
  <defaultValue>auto</defaultValue>
</leafNode>
<!-- include end -->
