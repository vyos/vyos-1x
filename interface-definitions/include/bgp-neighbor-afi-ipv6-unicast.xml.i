<!-- included start from bgp-neighbor-afi-ipv6-unicast.xml.i -->
<node name="ipv6-unicast">
  <properties>
    <help>IPv6 BGP neighbor parameters</help>
  </properties>
  <children>
    <node name="allowas-in">
      <properties>
        <help>Accept a IPv6-route that contains the local-AS in the as-path</help>
      </properties>
      <children>
        <leafNode name="number">
          <properties>
            <help>Number of occurrences of AS number</help>
            <valueHelp>
              <format>&lt;1-10&gt;</format>
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
        <help>AS for routes sent to this neighbor to be the local AS</help>
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
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this neighbor (IPv6)</help>
      </properties>
      <children>
        <node name="orf">
          <properties>
            <help>Advertise ORF capability to this neighbor</help>
          </properties>
          <children>
            <node name="prefix-list">
              <properties>
                <help>Advertise prefix-list ORF capability to this neighbor</help>
              </properties>
              <children>
                <leafNode name="receive">
                  <properties>
                    <help>Capability to receive the ORF</help>
                    <valueless/>
                  </properties>
                </leafNode>
                <leafNode name="send">
                  <properties>
                    <help>Capability to send the ORF</help>
                    <valueless/>
                  </properties>
                </leafNode>
              </children>
            </node>
          </children>
        </node>
      </children>
    </node>
    <node name="default-originate">
      <properties>
        <help>Send default IPv6-route to this neighbor</help>
      </properties>
      <children>
        <leafNode name="route-map">
          <properties>
            <help>Route-map to specify criteria of the default</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="disable-send-community">
      <properties>
        <help>Disable sending community attributes to this neighbor</help>
      </properties>
      <children>
        <leafNode name="extended">
          <properties>
            <help>Disable sending extended community attributes to this neighbor</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="standard">
          <properties>
            <help>Disable sending standard community attributes to this neighbor</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="distribute-list">
      <properties>
        <help>Access-list to filter route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>Access-list to filter outgoing route updates to this neighbor</help>
            <completionHelp>
              <path>policy access-list6</path>
            </completionHelp>
            <valueHelp>
              <format>&lt;1-65535&gt;</format>
              <description>Access-list to filter outgoing route updates to this neighbor</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Access-list to filter incoming route updates from this neighbor</help>
            <completionHelp>
              <path>policy access-list6</path>
            </completionHelp>
            <valueHelp>
              <format>&lt;1-65535&gt;</format>
              <description>Access-list to filter incoming route updates from this neighbor</description>
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
        <help>As-path-list to filter route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>As-path-list to filter outgoing route updates to this neighbor</help>
            <completionHelp>
              <path>policy as-path-list</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>As-path-list to filter incoming route updates from this neighbor</help>
            <completionHelp>
              <path>policy as-path-list</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="maximum-prefix">
      <properties>
        <help>Maximum number of prefixes to accept from this neighbor</help>
        <valueHelp>
          <format>&lt;1-4294967295&gt;</format>
          <description>Prefix limit</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="nexthop-local">
      <properties>
        <help>Nexthop attributes</help>
      </properties>
      <children>
        <leafNode name="unchanged">
          <properties>
            <help>Leave link-local nexthop unchanged for this peer</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="nexthop-self">
      <properties>
        <help>Nexthop for IPv6-routes sent to this neighbor to be the local router</help>
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
    <leafNode name="peer-group">
      <properties>
        <help>IPv6 peer group for this peer</help>
      </properties>
    </leafNode>
    <node name="prefix-list">
      <properties>
        <help>Prefix-list to filter route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>Prefix-list to filter outgoing route updates to this neighbor</help>
            <completionHelp>
              <path>policy prefix-list6</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Prefix-list to filter incoming route updates from this neighbor</help>
            <completionHelp>
              <path>policy prefix-list6</path>
            </completionHelp>
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
        <help>Route-map to filter route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>Route-map to filter outgoing route updates to this neighbor</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Route-map to filter incoming route updates from this neighbor</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="route-reflector-client">
      <properties>
        <help>Neighbor as a IPv6-route reflector client</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="route-server-client">
      <properties>
        <help>Neighbor is IPv6-route server client</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="soft-reconfiguration">
      <properties>
        <help>Soft reconfiguration for neighbor (IPv6)</help>
      </properties>
      <children>
        <leafNode name="inbound">
          <properties>
            <help>Inbound soft reconfiguration for this neighbor [REQUIRED]</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="unsuppress-map">
      <properties>
        <help>Route-map to selectively unsuppress suppressed IPv6-routes</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="weight">
      <properties>
        <help>Default weight for routes from this neighbor</help>
        <valueHelp>
          <format>&lt;1-65535&gt;</format>
          <description>Weight for routes from this neighbor</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
