<!-- include start from firewall/tcp-mss.xml.i -->
<node name="tcp">
  <properties>
    <help>TCP options to match</help>
  </properties>
  <children>
    <leafNode name="mss">
      <properties>
        <help>Maximum segment size (MSS)</help>
        <valueHelp>
          <format>u32:1-16384</format>
          <description>Maximum segment size</description>
        </valueHelp>
        <valueHelp>
          <format>&lt;min&gt;-&lt;max&gt;</format>
          <description>TCP MSS range (use '-' as delimiter)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 1-16384"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
