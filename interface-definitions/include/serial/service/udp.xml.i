<!-- include start from serial/service/udp.xml.i -->
<node name="udp">
  <properties>
    <help>UDP profile</help>
  </properties>
  <children>
    <leafNode name="multicast-interface">
      <properties>
        <help>Ethernet Interface for multicast</help>
        <valueHelp>
          <format>ethN</format>
          <description>Ethernet interface name</description>
        </valueHelp>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces --type ethernet</script>
        </completionHelp>
        <constraint>
          <regex>eth[0-9]+</regex>
        </constraint>
        <constraintErrorMessage>Invalid Ethernet interface name</constraintErrorMessage>
      </properties>
    </leafNode>
    <tagNode name="entry">
      <properties>
        <help>UDP rule entry</help>
        <valueHelp>
          <format>u32:1-4</format>
          <description>Entry ID (1-4)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-4"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="disable">
          <properties>
            <help>Disable this entry</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="direction">
          <properties>
            <help>UDP direction</help>
            <completionHelp>
              <list>both lan-serial serial-lan</list>
            </completionHelp>
            <constraint>
              <regex>(both|lan-serial|serial-lan)</regex>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="udp-port">
          <properties>
            <help>UDP port option</help>
            <completionHelp>
              <list>auto-learn any</list>
            </completionHelp>
            <valueHelp>
              <format>auto-learn</format>
              <description>auto-learn [does not apply to out direction]</description>
            </valueHelp>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Specific port number</description>
            </valueHelp>
            <valueHelp>
              <format>any</format>
              <description>any [apply to in direction only]</description>
            </valueHelp>
            <constraint>
              <validator name="udp-port-option"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="start-address">
          <properties>
            <help>UDP Start Host IP</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IP address of current host</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address of current host</description>
            </valueHelp>
            <constraint>
              <validator name="ip-address"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="end-address">
          <properties>
            <help>UDP End Host IP</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IP address of current host</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address of current host</description>
            </valueHelp>
            <constraint>
              <validator name="ip-address"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
