<!-- include start from serial/service/reverse.xml.i -->
<node name="reverse">
  <properties>
    <help>Reverse connection profile</help>
  </properties>
  <children>
    <leafNode name="enable-auth-user">
      <properties>
        <help>Enable authenticate user</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="inet">
      <properties>
        <help>IP Address</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address</description>
        </valueHelp>
        <constraint>
          <validator name="ip-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    #include <include/serial/service/utils/multisession.xml.i>
    <leafNode name="allow-multiple-connection">
      <properties>
        <help>Enable allow multiple connections</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
