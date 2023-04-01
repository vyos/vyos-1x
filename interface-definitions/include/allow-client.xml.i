<!-- include start from allow-client.xml.i -->
<node name="allow-client">
  <properties>
    <help>Restrict to allowed IP client addresses</help>
  </properties>
  <children>
    <leafNode name="address">
      <properties>
        <help>Allowed IP client addresses</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 address and prefix length</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ip-address"/>
          <validator name="ip-cidr"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
