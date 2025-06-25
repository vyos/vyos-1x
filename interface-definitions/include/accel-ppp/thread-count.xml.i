<!-- include start from accel-ppp/thread-count.xml.i -->
<leafNode name="thread-count">
  <properties>
    <help>Number of working threads</help>
    <completionHelp>
      <list>all half</list>
    </completionHelp>
    <valueHelp>
      <format>all</format>
      <description>Use all available CPU cores</description>
    </valueHelp>
    <valueHelp>
      <format>half</format>
      <description>Use half of available CPU cores</description>
    </valueHelp>
    <valueHelp>
      <format>u32:1-512</format>
      <description>Thread count</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-512"/>
      <regex>(all|half)</regex>
    </constraint>
  </properties>
  <defaultValue>all</defaultValue>
</leafNode>
<!-- include end -->
