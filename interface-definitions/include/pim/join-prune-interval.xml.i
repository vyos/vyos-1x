<!-- include start from pim/join-prune-interval.xml.i -->
<leafNode name="join-prune-interval">
  <properties>
    <help>Join prune send interval</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Interval in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
  <defaultValue>60</defaultValue>
</leafNode>
<!-- include end -->
