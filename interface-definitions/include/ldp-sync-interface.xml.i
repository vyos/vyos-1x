<!-- include start from ldp-igp-sync.xml.i -->
<node name="ldp-sync">
  <properties>
    <help>LDP-IGP synchronization configuration for interface</help>
  </properties>
  <children>
    #include <include/generic-disable-node.xml.i>
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
  </children>
</node>
<!-- include end -->
