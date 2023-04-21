<!-- include start from isis/ldp-sync-holddown.xml.i -->
<leafNode name="holddown">
  <properties>
    <help>Hold down timer for LDP-IGP cost restoration</help>
    <valueHelp>
      <format>u32:0-10000</format>
      <description>Time to wait in seconds for LDP-IGP synchronization to occur before restoring interface cost</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-10000"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
