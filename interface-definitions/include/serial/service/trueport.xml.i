<!-- include start from serial/service/trueport.xml.i -->
<node name="trueport">
  <properties>
    <help>Trueport profile</help>
  </properties>
  <children>
    <leafNode name="signal-active">
      <properties>
        <help>Enable raise signals when not under trueport client control</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="allow-multiple-connection">
      <properties>
        <help>Allow multiple connections [client init only] [trueport lite only]</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="main-hostport">
      <properties>
        <help>Connect to main host port [server init only]</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Port number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="main-hostname">
      <properties>
        <help>Connect to main host [server init only]</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IP address of main host</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of main host</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>Fully qualified host name of main host</description>
        </valueHelp>
        <constraint>
          <validator name="ip-address"/>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="multihost">
      <properties>
        <help>Connect to multiple hosts [server init only] [trueport lite only]</help>
      </properties>
      <children>
        #include <include/serial/service/utils/multihost.xml.i>
      </children>
    </node>

  </children>
</node>
<!-- include end -->
