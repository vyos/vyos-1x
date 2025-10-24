<!-- include start from include/failover/common-failover.xml.i -->
<children>
  <node name="check">
    <properties>
      <help>Check target options</help>
    </properties>
    <children>
      <leafNode name="policy">
        <properties>
          <help>Policy for check targets</help>
          <completionHelp>
            <list>any-available all-available</list>
          </completionHelp>
          <valueHelp>
            <format>all-available</format>
            <description>All targets must be alive</description>
          </valueHelp>
          <valueHelp>
            <format>any-available</format>
            <description>Any target must be alive</description>
          </valueHelp>
          <constraint>
            <regex>(all-available|any-available)</regex>
          </constraint>
        </properties>
        <defaultValue>any-available</defaultValue>
      </leafNode>
      #include <include/port-number.xml.i>
      <tagNode name="target">
        <properties>
          <help>Check target address</help>
          <valueHelp>
            <format>ipv4</format>
            <description>Address to check</description>
          </valueHelp>
          <constraint>
            <validator name="ipv4-address"/>
          </constraint>
        </properties>
        <children>
          #include <include/interface/vrf.xml.i>
          #include <include/generic-interface.xml.i>
        </children>
      </tagNode>
      <leafNode name="timeout">
        <properties>
          <help>Timeout between checks</help>
          <valueHelp>
            <format>u32:1-300</format>
            <description>Timeout in seconds between checks</description>
          </valueHelp>
          <constraint>
            <validator name="numeric" argument="--range 1-255"/>
          </constraint>
        </properties>
        <defaultValue>10</defaultValue>
      </leafNode>
      <leafNode name="type">
        <properties>
          <help>Check type</help>
          <completionHelp>
            <list>arp icmp tcp</list>
          </completionHelp>
          <valueHelp>
            <format>arp</format>
            <description>Check target by ARP</description>
          </valueHelp>
          <valueHelp>
            <format>icmp</format>
            <description>Check target by ICMP</description>
          </valueHelp>
          <valueHelp>
            <format>tcp</format>
            <description>Check target by TCP</description>
          </valueHelp>
          <constraint>
            <regex>(arp|icmp|tcp)</regex>
          </constraint>
        </properties>
        <defaultValue>icmp</defaultValue>
      </leafNode>
    </children>
  </node>
  #include <include/generic-interface.xml.i>
  <leafNode name="metric">
    <properties>
      <help>Route metric for this gateway</help>
      <valueHelp>
        <format>u32:1-255</format>
        <description>Route metric</description>
      </valueHelp>
      <constraint>
        <validator name="numeric" argument="--range 1-255"/>
      </constraint>
    </properties>
    <defaultValue>1</defaultValue>
  </leafNode>
  <leafNode name="onlink">
    <properties>
      <help>The next hop is directly connected to the interface, even if it does not match interface prefix</help>
      <valueless/>
    </properties>
  </leafNode>
</children>
<!-- include end -->
