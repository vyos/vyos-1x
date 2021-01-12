<!-- included start from bgp-afi-common.xml.i -->
<node name="allowas-in">
  <properties>
    <help>Accept route that contains the local-as in the as-path</help>
  </properties>
  <children>
    <leafNode name="number">
      <properties>
        <help>Number of occurrences of AS number</help>
        <valueHelp>
          <format>u32:1-10</format>
          <description>Number of times AS is allowed in path</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-10"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="as-override">
  <properties>
    <help>AS for routes sent to this peer to be the local AS</help>
    <valueless/>
  </properties>
</leafNode>
<node name="attribute-unchanged">
  <properties>
    <help>BGP attributes are sent unchanged</help>
  </properties>
  <children>
    <leafNode name="as-path">
      <properties>
        <help>Send AS path unchanged</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="med">
      <properties>
        <help>Send multi-exit discriminator unchanged</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="next-hop">
      <properties>
        <help>Send nexthop unchanged</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
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
<node name="default-originate">
  <properties>
    <help>Originate default route to this peer</help>
  </properties>
  <children>
    <leafNode name="route-map">
      <properties>
        <help>route-map to specify criteria of the default route</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
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
<node name="filter-list">
  <properties>
    <help>as-path-list to filter route updates to/from this peer</help>
  </properties>
  <children>
    <leafNode name="export">
      <properties>
        <help>As-path-list to filter outgoing route updates to this peer</help>
        <completionHelp>
          <path>policy as-path-list</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="import">
      <properties>
        <help>As-path-list to filter incoming route updates from this peer</help>
        <completionHelp>
          <path>policy as-path-list</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
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
<node name="nexthop-self">
  <properties>
    <help>Disable the next hop calculation for this peer</help>
  </properties>
  <children>
    <leafNode name="force">
      <properties>
        <help>Set the next hop to self for reflected routes</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="remove-private-as">
  <properties>
    <help>Remove private AS numbers from AS path in outbound route updates</help>
    <valueless/>
  </properties>
</leafNode>
<node name="route-map">
  <properties>
    <help>Route-map to filter route updates to/from this peer</help>
  </properties>
  <children>
    <leafNode name="export">
      <properties>
        <help>Route-map to filter outgoing route updates</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="import">
      <properties>
        <help>Route-map to filter incoming route updates</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="route-reflector-client">
  <properties>
    <help>Peer is a route reflector client</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="route-server-client">
  <properties>
    <help>Peer is a route server client</help>
    <valueless/>
  </properties>
</leafNode>
<node name="soft-reconfiguration">
  <properties>
    <help>Soft reconfiguration for peer</help>
  </properties>
  <children>
    <leafNode name="inbound">
      <properties>
        <help>Enable inbound soft reconfiguration</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="unsuppress-map">
  <properties>
    <help>Route-map to selectively unsuppress suppressed routes</help>
    <valueless/>
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
<!-- included end -->
