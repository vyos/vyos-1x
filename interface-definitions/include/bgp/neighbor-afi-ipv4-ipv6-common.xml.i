<!-- include start from bgp/neighbor-afi-ipv4-ipv6-common.xml.i -->
<leafNode name="addpath-tx-all">
  <properties>
    <help>Use addpath to advertise all paths to a neighbor</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="addpath-tx-per-as">
  <properties>
    <help>Use addpath to advertise the bestpath per each neighboring AS</help>
    <valueless/>
  </properties>
</leafNode>
<node name="conditionally-advertise">
  <properties>
    <help>Use route-map to conditionally advertise routes</help>
  </properties>
  <children>
    <leafNode name="advertise-map">
      <properties>
        <help>Route-map to conditionally advertise routes</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Route map name</description>
        </valueHelp>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
        <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="exist-map">
      <properties>
        <help>Advertise routes only if prefixes in exist-map are installed in BGP table</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Route map name</description>
        </valueHelp>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
        <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="non-exist-map">
      <properties>
        <help>Advertise routes only if prefixes in non-exist-map are not installed in BGP table</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Route map name</description>
        </valueHelp>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
        <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
#include <include/bgp/afi-allowas-in.xml.i>
<leafNode name="as-override">
  <properties>
    <help>Override ASN in outbound updates to configured neighbor local-as</help>
    <valueless/>
  </properties>
</leafNode>
#include <include/bgp/afi-attribute-unchanged.xml.i>
<node name="disable-send-community">
  <properties>
    <help>Disable sending community attributes to this peer</help>
  </properties>
  <children>
    <leafNode name="extended">
      <properties>
        <help>Disable sending extended community attributes to this peer</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="standard">
      <properties>
        <help>Disable sending standard community attributes to this peer</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<node name="distribute-list">
  <properties>
    <help>Access-list to filter route updates to/from this peer-group</help>
  </properties>
  <children>
    <leafNode name="export">
      <properties>
        <help>Access-list to filter outgoing route updates to this peer-group</help>
        <completionHelp>
          <path>policy access-list</path>
        </completionHelp>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Access-list to filter outgoing route updates to this peer-group</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="import">
      <properties>
        <help>Access-list to filter incoming route updates from this peer-group</help>
        <completionHelp>
          <path>policy access-list</path>
        </completionHelp>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Access-list to filter incoming route updates from this peer-group</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
#include <include/bgp/afi-filter-list.xml.i>
<leafNode name="maximum-prefix">
  <properties>
    <help>Maximum number of prefixes to accept from this peer</help>
    <valueHelp>
      <format>u32:1-4294967295</format>
      <description>Prefix limit</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967295"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="maximum-prefix-out">
  <properties>
    <help>Maximum number of prefixes to be sent to this peer</help>
    <valueHelp>
      <format>u32:1-4294967295</format>
      <description>Prefix limit</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967295"/>
    </constraint>
  </properties>
</leafNode>
#include <include/bgp/afi-nexthop-self.xml.i>
<node name="remove-private-as">
  <properties>
    <help>Remove private AS numbers from AS path in outbound route updates</help>
  </properties>
  <children>
    <leafNode name="all">
      <properties>
        <help>Remove private AS numbers to all AS numbers in outbound route updates</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
#include <include/bgp/afi-route-map.xml.i>
#include <include/bgp/afi-route-reflector-client.xml.i>
#include <include/bgp/afi-route-server-client.xml.i>
#include <include/bgp/afi-soft-reconfiguration.xml.i>
<leafNode name="unsuppress-map">
  <properties>
    <help>Route-map to selectively unsuppress suppressed routes</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Route map name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
    <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
  </properties>
</leafNode>
<leafNode name="weight">
  <properties>
    <help>Default weight for routes from this peer</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Default weight</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
