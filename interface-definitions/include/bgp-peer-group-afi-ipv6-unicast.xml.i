<!-- included start from bgp-peer-group-afi-ipv6-unicast.xml.i -->
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
        <help>Advertise capabilities to this peer-group</help>
      </properties>
      <children>
        <leafNode name="dynamic">
          <properties>
            <help>Advertise dynamic capability to this peer-group</help>
            <valueless/>
          </properties>
        </leafNode>
        <node name="orf">
          <properties>
            <help>Advertise ORF capability to this peer-group</help>
          </properties>
          <children>
            <node name="prefix-list">
              <properties>
                <help>Advertise prefix-list ORF capability to this peer-group</help>
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
        <help>Send default route to this peer-group</help>
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
        <help>Disable sending community attributes to this peer-group</help>
      </properties>
      <children>
        <leafNode name="extended">
          <properties>
            <help>Disable sending extended community attributes to this peer-group</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="standard">
          <properties>
            <help>Disable sending standard community attributes to this peer-group</help>
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
              <path>policy access-list6</path>
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
              <path>policy access-list6</path>
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
        <help>As-path-list to filter route updates to/from this peer-group</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>As-path-list to filter outgoing route updates to this peer-group</help>
            <completionHelp>
              <path>policy as-path-list</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>As-path-list to filter incoming route updates from this peer-group</help>
            <completionHelp>
              <path>policy as-path-list</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="maximum-prefix">
      <properties>
        <help>Maximum number of prefixes to accept from this peer-group</help>
        <valueHelp>
          <format>u32:1-4294967295</format>
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
        <help>Nexthop for routes sent to this peer-group to be the local router</help>
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
    <node name="prefix-list">
      <properties>
        <help>Prefix-list to filter route updates to/from this peer-group</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>Prefix-list to filter outgoing route updates to this peer-group</help>
            <completionHelp>
              <path>policy prefix-list6</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Prefix-list to filter incoming route updates from this peer-group</help>
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
        <help>Route-map to filter route updates to/from this peer-group</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>Route-map to filter outgoing route updates to this peer-group</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Route-map to filter incoming route updates from this peer-group</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="route-reflector-client">
      <properties>
        <help>Peer-group as a route reflector client</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="route-server-client">
      <properties>
        <help>Peer-group as route server client</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="soft-reconfiguration">
      <properties>
        <help>Soft reconfiguration for peer-group</help>
      </properties>
      <children>
        <leafNode name="inbound">
          <properties>
            <help>Inbound soft reconfiguration for this peer-group [REQUIRED]</help>
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
        <help>Default weight for routes from this peer-group</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Weight for routes from this peer-group</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
