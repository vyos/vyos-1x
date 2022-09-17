<!-- include start from qos/limiter-actions.xml.i -->
<leafNode name="exceed-action">
  <properties>
    <help>Default action for packets exceeding the limiter (default: drop)</help>
    <completionHelp>
      <list>continue drop ok reclassify pipe</list>
    </completionHelp>
    <valueHelp>
      <format>continue</format>
      <description>Don't do anything, just continue with the next action in line</description>
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
<leafNode name="notexceed-action">
  <properties>
    <help>Default action for packets not exceeding the limiter (default: ok)</help>
    <completionHelp>
      <list>continue drop ok reclassify pipe</list>
    </completionHelp>
    <valueHelp>
      <format>continue</format>
      <description>Don't do anything, just continue with the next action in line</description>
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
