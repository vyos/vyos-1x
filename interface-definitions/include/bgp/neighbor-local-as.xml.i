<!-- include start from bgp/neighbor-local-as.xml.i -->
<tagNode name="local-as">
  <properties>
    <help>Specify alternate ASN for this BGP process</help>
    <valueHelp>
      <format>u32:1-4294967294</format>
      <description>Autonomous System Number (ASN)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967294"/>
    </constraint>
  </properties>
  <children>
    <node name="no-prepend">
      <properties>
        <help>Disable prepending local-as from/to updates for eBGP peers</help>
      </properties>
      <children>
        <leafNode name="replace-as">
          <properties>
            <help>Prepend only local-as from/to updates for eBGP peers</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</tagNode>
<!-- include end -->
