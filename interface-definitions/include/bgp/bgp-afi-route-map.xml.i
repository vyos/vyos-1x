<!-- include start from bgp-afi-route-map.xml.i -->
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
<!-- include end -->
