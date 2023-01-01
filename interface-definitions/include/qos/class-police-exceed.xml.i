<!-- include start from qos/police.xml.i -->
<leafNode name="exceed">
  <properties>
    <help>Default action for packets exceeding the limiter</help>
    <completionHelp>
      <list>continue drop ok reclassify pipe</list>
    </completionHelp>
    <valueHelp>
      <format>continue</format>
      <description>Do not do anything, just continue with the next action in line</description>
    </valueHelp>
    <valueHelp>
      <format>drop</format>
      <description>Drop the packet immediately</description>
    </valueHelp>
    <valueHelp>
      <format>ok</format>
      <description>Accept the packet</description>
    </valueHelp>
    <valueHelp>
      <format>reclassify</format>
      <description>Treat the packet as non-matching to the filter this action is attached to and continue with the next filter in line (if any)</description>
    </valueHelp>
    <valueHelp>
      <format>pipe</format>
      <description>Pass the packet to the next action in line</description>
    </valueHelp>
    <constraint>
      <regex>(continue|drop|ok|reclassify|pipe)</regex>
    </constraint>
  </properties>
  <defaultValue>drop</defaultValue>
</leafNode>
<leafNode name="not-exceed">
  <properties>
    <help>Default action for packets not exceeding the limiter</help>
    <completionHelp>
      <list>continue drop ok reclassify pipe</list>
    </completionHelp>
    <valueHelp>
      <format>continue</format>
      <description>Do not do anything, just continue with the next action in line</description>
    </valueHelp>
    <valueHelp>
      <format>drop</format>
      <description>Drop the packet immediately</description>
    </valueHelp>
    <valueHelp>
      <format>ok</format>
      <description>Accept the packet</description>
    </valueHelp>
    <valueHelp>
      <format>reclassify</format>
      <description>Treat the packet as non-matching to the filter this action is attached to and continue with the next filter in line (if any)</description>
    </valueHelp>
    <valueHelp>
      <format>pipe</format>
      <description>Pass the packet to the next action in line</description>
    </valueHelp>
    <constraint>
      <regex>(continue|drop|ok|reclassify|pipe)</regex>
    </constraint>
  </properties>
  <defaultValue>ok</defaultValue>
</leafNode>
<!-- include end -->
