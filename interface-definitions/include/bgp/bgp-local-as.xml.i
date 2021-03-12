<!-- include start from bgp-local-as.xml.i -->
<tagNode name="local-as">
  <properties>
    <help>Local AS number [REQUIRED]</help>
    <valueHelp>
      <format>u32:1-4294967294</format>
      <description>Local AS number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967294"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="no-prepend">
      <properties>
        <help>Disable prepending local-as to updates from EBGP peers</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
