<!-- included start from bgp-neighbor-afi-ipv4-unicast.xml.i -->
<node name="ipv4-unicast">
  <properties>
    <help>IPv4 BGP neighbor parameters</help>
  </properties>
  <children>
    <node name="allowas-in">
      <properties>
        <help>Accept a IPv4-route that contains the local-AS in the as-path</help>
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
        <help>BGP attributes are sent unchanged (IPv4)</help>
      </properties>
      <children>
        <leafNode name="as-path">
          <properties>
            <help>Send AS path unchanged (IPv4)</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="med">
          <properties>
            <help>Send multi-exit discriminator unchanged (IPv4)</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="next-hop">
          <properties>
            <help>Send nexthop unchanged (IPv4)</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this neighbor (IPv4)</help>
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
        <help>Send default IPv4-route to this neighbor</help>
      </properties>
      <children>
        <leafNode name="route-map">
          <properties>
            <help>IPv4-Route-map to specify criteria of the default</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="distribute-list">
      <properties>
        <help>Access-list to filter IPv4-route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>Access-list to filter outgoing IPv4-route updates to this neighbor</help>
            <completionHelp>
              <path>policy access-list</path>
            </completionHelp>
            <valueHelp>
              <format>&lt;1-65535&gt;</format>
              <description>Access-list to filter outgoing IPv4-route updates to this neighbor</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Access-list to filter incoming IPv4-route updates from this neighbor</help>
            <completionHelp>
              <path>policy access-list</path>
            </completionHelp>
            <valueHelp>
              <format>&lt;1-65535&gt;</format>
              <description>Access-list to filter incoming IPv4-route updates from this neighbor</description>
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
        <help>As-path-list to filter IPv4-route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>As-path-list to filter outgoing IPv4-route updates to this neighbor</help>
            <completionHelp>
              <path>policy as-path-list</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>As-path-list to filter incoming IPv4-route updates from this neighbor</help>
            <completionHelp>
              <path>policy as-path-list</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="maximum-prefix">
      <properties>
        <help>Maximum number of IPv4-prefixes to accept from this neighbor</help>
        <valueHelp>
          <format>&lt;1-4294967295&gt;</format>
          <description>Prefix limit</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="nexthop-self">
      <properties>
        <help>Nexthop for IPv4-routes sent to this neighbor to be the local router</help>
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
        <help>IPv4-Prefix-list to filter route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>IPv4-Prefix-list to filter outgoing route updates to this neighbor</help>
            <completionHelp>
              <path>policy prefix-list</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>IPv4-Prefix-list to filter incoming route updates from this neighbor</help>
            <completionHelp>
              <path>policy prefix-list</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="remove-private-as">
      <properties>
        <help>Remove private AS numbers from AS path in outbound IPv4-route updates</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="route-map">
      <properties>
        <help>Route-map to filter IPv4-route updates to/from this neighbor</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>IPv4-Route-map to filter outgoing route updates to this neighbor</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>IPv4-Route-map to filter incoming route updates from this neighbor</help>
            <completionHelp>
              <path>policy route-map</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="route-reflector-client">
      <properties>
        <help>Neighbor as a IPv4-route reflector client</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="route-server-client">
      <properties>
        <help>Neighbor is IPv4-route server client</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="soft-reconfiguration">
      <properties>
        <help>Soft reconfiguration for neighbor (IPv4)</help>
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
        <help>Route-map to selectively unsuppress suppressed IPv4-routes</help>
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
