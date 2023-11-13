<!-- include start from pim/hello.xml.i -->
<leafNode name="hello">
  <properties>
    <help>Hello Interval</help>
    <valueHelp>
      <format>u32:1-180</format>
      <description>Hello Interval in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-180"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
