<!-- include start from firewall/set-packet-modifications-table-and-vrf.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="table">
      <properties>
        <help>Set the routing table for matched packets</help>
        <valueHelp>
          <format>u32:1-200</format>
          <description>Table number</description>
        </valueHelp>
        <valueHelp>
          <format>main</format>
          <description>Main table</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-200"/>
          <regex>(main)</regex>
        </constraint>
        <completionHelp>
          <list>main</list>
          <path>protocols static table</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="vrf">
      <properties>
        <help>VRF to forward packet with</help>
        <valueHelp>
          <format>txt</format>
          <description>VRF instance name</description>
        </valueHelp>
        <valueHelp>
          <format>default</format>
          <description>Forward into default global VRF</description>
        </valueHelp>
        <completionHelp>
          <list>default</list>
          <path>vrf name</path>
        </completionHelp>
        #include <include/constraint/vrf.xml.i>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
