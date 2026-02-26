<!-- include start from serial/service/direct.xml.i -->
<node name="direct">
  <properties>
    <help>Direct connection profile</help>
  </properties>
  <children>
    <leafNode name="main-hostport">
      <properties>
        <help>Connect to main host port</help>
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
        <help>Connect to main host</help>
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
    <node name="tcp">
      <properties>
        <help>tcp settings</help>
      </properties>
      <children>
        <node name="multihost">
          <properties>
            <help>Connect to multiple hosts [tcp only]</help>
          </properties>
          <children>
            #include <include/serial/service/utils/multihost.xml.i>
          </children>
        </node>
      </children>
    </node>
    <node name="telnet">
      <properties>
        <help>telnet settings</help>
      </properties>
      <children>
        #include <include/serial/service/utils/term-type.xml.i>
        <leafNode name="map-cr-to-crlf">
          <properties>
            <help>Enable mapping carriage returns (CR) to carriage return line feed (CRLF)</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="ssh">
      <properties>
        <help>ssh settings</help>
      </properties>
      <children>
        #include <include/serial/service/utils/term-type.xml.i>
        <leafNode name="login-name">
          <properties>
            <help>Specifies the user to log in as on the remote machine</help>
            <constraint>
              <regex>.{0,21}</regex>
            </constraint>
            <constraintErrorMessage>Login username string too long (limit 21 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="initiate-any-char">
      <properties>
        <help>Connect when any data is received [main only]</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="initiate-specific-char">
      <properties>
        <help>Connect when specific character received [main only]</help>
        <valueHelp>
          <format>txt</format>
          <description>ASCII char in hex value</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
