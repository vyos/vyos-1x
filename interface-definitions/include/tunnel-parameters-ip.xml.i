<!-- included start from tunnel-parameters-ip.xml.i -->
<node name="ip">
  <properties>
    <help>IPv4 specific tunnel parameters</help>
  </properties>
  <children>
    <leafNode name="ttl">
      <properties>
        <help>Time to live field</help>
        <valueHelp>
          <format>0-255</format>
          <description>Time to live (default 255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
        <constraintErrorMessage>TTL must be between 0 and 255</constraintErrorMessage>
      </properties>
      <defaultValue>255</defaultValue>
    </leafNode>
    <leafNode name="tos">
      <properties>
        <help>Type of Service (TOS)</help>
        <valueHelp>
          <format>0-99</format>
          <description>Type of Service (TOS)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-99"/>
        </constraint>
        <constraintErrorMessage>TOS must be between 0 and 99</constraintErrorMessage>
      </properties>
      <defaultValue>inherit</defaultValue>
    </leafNode>
    <leafNode name="key">
      <properties>
        <help>Tunnel key</help>
        <valueHelp>
          <format>u32</format>
          <description>Tunnel key</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
        <constraintErrorMessage>key must be between 0-4294967295</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
