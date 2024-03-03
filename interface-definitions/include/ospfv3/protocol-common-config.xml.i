<!-- include start from ospfv3/protocol-common-config.xml.i -->
<tagNode name="area">
  <properties>
    <help>OSPFv3 Area</help>
    <valueHelp>
      <format>u32</format>
      <description>Area ID as a decimal value</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4</format>
      <description>Area ID in IP address forma</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967295"/>
      <validator name="ip-address"/>
    </constraint>
  </properties>
  <children>
    <node name="area-type">
      <properties>
        <help>OSPFv3 Area type</help>
      </properties>
      <children>
        <node name="nssa">
          <properties>
            <help>NSSA OSPFv3 area</help>
          </properties>
          <children>
            <leafNode name="default-information-originate">
              <properties>
                <help>Originate Type 7 default into NSSA area</help>
                <valueless/>
              </properties>
            </leafNode>
            #include <include/ospfv3/no-summary.xml.i>
          </children>
        </node>
        <node name="stub">
          <properties>
            <help>Stub OSPFv3 area</help>
          </properties>
          <children>
            #include <include/ospfv3/no-summary.xml.i>
          </children>
        </node>
      </children>
    </node>
    <leafNode name="export-list">
      <properties>
        <help>Name of export-list</help>
        <completionHelp>
          <path>policy access-list6</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="import-list">
      <properties>
        <help>Name of import-list</help>
        <completionHelp>
          <path>policy access-list6</path>
        </completionHelp>
      </properties>
    </leafNode>
    <tagNode name="range">
      <properties>
        <help>Specify IPv6 prefix (border routers only)</help>
        <valueHelp>
          <format>ipv6net</format>
          <description>Specify IPv6 prefix (border routers only)</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-prefix"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="advertise">
          <properties>
            <help>Advertise this range</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="not-advertise">
          <properties>
            <help>Do not advertise this range</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</tagNode>
#include <include/ospf/auto-cost.xml.i>
#include <include/ospf/default-information.xml.i>
<node name="distance">
  <properties>
    <help>Administrative distance</help>
  </properties>
  <children>
    #include <include/ospf/distance-global.xml.i>
    <node name="ospfv3">
      <properties>
        <help>OSPFv3 administrative distance</help>
      </properties>
      <children>
        #include <include/ospf/distance-per-protocol.xml.i>
      </children>
    </node>
  </children>
</node>
#include <include/ospf/graceful-restart.xml.i>
<node name="graceful-restart">
  <children>
    <node name="helper">
      <children>
        <leafNode name="lsa-check-disable">
          <properties>
            <help>Disable strict LSA check</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<tagNode name="interface">
  <properties>
    <help>Enable routing on an IPv6 interface</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface used for routing information exchange</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
  <children>
    <leafNode name="area">
      <properties>
        <help>Enable OSPF on this interface</help>
        <completionHelp>
          <path>protocols ospfv3 area</path>
        </completionHelp>
        <valueHelp>
          <format>u32</format>
          <description>OSPF area ID as decimal notation</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4</format>
          <description>OSPF area ID in IP address notation</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
          <validator name="ip-address"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/ospf/intervals.xml.i>
    #include <include/ospf/interface-common.xml.i>
    <leafNode name="ifmtu">
      <properties>
        <help>Interface MTU</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Interface MTU</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="instance-id">
      <properties>
        <help>Instance ID</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>Instance Id</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
    <leafNode name="network">
      <properties>
        <help>Network type</help>
        <completionHelp>
          <list>broadcast point-to-point</list>
        </completionHelp>
        <valueHelp>
          <format>broadcast</format>
          <description>Broadcast network type</description>
        </valueHelp>
        <valueHelp>
          <format>point-to-point</format>
          <description>Point-to-point network type</description>
        </valueHelp>
        <constraint>
          <regex>(broadcast|point-to-point)</regex>
        </constraint>
        <constraintErrorMessage>Must be broadcast or point-to-point</constraintErrorMessage>
      </properties>
    </leafNode>
    #include <include/isis/passive.xml.i>
  </children>
</tagNode>
#include <include/ospf/log-adjacency-changes.xml.i>
<node name="parameters">
  <properties>
    <help>OSPFv3 specific parameters</help>
  </properties>
  <children>
    #include <include/router-id.xml.i>
  </children>
</node>
<node name="redistribute">
  <properties>
    <help>Redistribute information from another routing protocol</help>
  </properties>
  <children>
    <node name="babel">
      <properties>
        <help>Redistribute Babel routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="bgp">
      <properties>
        <help>Redistribute BGP routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="connected">
      <properties>
        <help>Redistribute connected routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="isis">
      <properties>
        <help>Redistribute IS-IS routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="kernel">
      <properties>
        <help>Redistribute kernel routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="ripng">
      <properties>
        <help>Redistribute RIPNG routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="static">
      <properties>
        <help>Redistribute static routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
