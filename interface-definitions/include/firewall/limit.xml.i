<!-- include start from firewall/limit.xml.i -->
<node name="limit">
  <properties>
    <help>Rate limit using a token bucket filter</help>
  </properties>
  <children>
    <leafNode name="burst">
      <properties>
        <help>Maximum number of packets to allow in excess of rate</help>
        <valueHelp>
          <format>u32:0-4294967295</format>
          <description>Maximum number of packets to allow in excess of rate</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="rate">
      <properties>
        <help>Maximum average matching rate</help>
        <valueHelp>
          <format>txt</format>
          <description>integer/unit (Example: 5/minute)</description>
        </valueHelp>
        <constraint>
          <regex>\d+/(second|minute|hour|day)</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->