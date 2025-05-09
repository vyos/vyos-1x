<!-- include start from serial/service/modbus.xml.i -->
<node name="modbus">
  <properties>
    <help>Modbus profile</help>
  </properties>
  <children>
    #include <include/serial/service/utils/ip-aliasing.xml.i>
    <leafNode name="ascii-crlf">
      <properties>
        <help>Enable append CR/LF to the end of the transmission in ASCII mode</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="protocol">
      <properties>
        <help>Protocol</help>
        <completionHelp>
          <list>RTU ASCII</list>
        </completionHelp>
        <constraint>
          <regex>(RTU|ASCII)</regex>
        </constraint>
      </properties>
      <defaultValue>RTU</defaultValue>
    </leafNode>
    <leafNode name="uid-range">
      <properties>
        <help>Slave UID range [slave only]</help>
        <valueHelp>
          <format>start-end</format>
          <description>UID range (e.g. 2-5) to match</description>
        </valueHelp>
        <constraint>
          <validator name="modbus-uid-range"/>
        </constraint>
      </properties>
    </leafNode>
    <tagNode name="slave-mapping-list">
      <properties>
        <help>Modbus slave mapping list [master only]</help>
        <valueHelp>
          <!-- table main with prio 32766 -->
          <format>u32:1-16</format>
          <description>Mapping ID (1-16)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-16"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="protocol">
          <properties>
            <help>Protocol</help>
            <completionHelp>
              <list>TCP UDP</list>
            </completionHelp>
            <constraint>
              <regex>(TCP|UDP)</regex>
            </constraint>
          </properties>
          <defaultValue>TCP</defaultValue>
        </leafNode>
        <leafNode name="range-mode">
          <properties>
            <help>Specify the configuration of the Modbus Slaves on the network</help>
            <completionHelp>
              <list>host gateway</list>
            </completionHelp>
            <constraint>
              <regex>(host|gateway)</regex>
            </constraint>
          </properties>
          <defaultValue>host</defaultValue>
        </leafNode>
        <leafNode name="port">
          <properties>
            <help>Multihost host tcp port</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Port number</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="slave-ip">
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
        <leafNode name="uid-range">
          <properties>
            <help>Slave UID range</help>
            <valueHelp>
              <format>start-end</format>
              <description>UID range (e.g. 2-5) to match</description>
            </valueHelp>
            <constraint>
              <validator name="modbus-uid-range"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
