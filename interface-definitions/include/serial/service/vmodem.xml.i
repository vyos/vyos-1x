<!-- include start from serial/service/vmodem.xml.i -->
<node name="vmodem">
  <properties>
    <help>Virtual Modem profile</help>
  </properties>
  <children>
    <leafNode name="echo">
      <properties>
        <help>Enable echo characters in command mode</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="failure-string">
      <properties>
        <help>String that is sent to the serial device when a connection fails</help>
        <constraint>
          <regex>.{0,30}</regex>
        </constraint>
        <constraintErrorMessage>Vmodem failure string too long (limit 30 characters)</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="success-string">
      <properties>
        <help>String that is sent to the serial device when a connection succeeds</help>
        <constraint>
          <regex>.{0,40}</regex>
        </constraint>
        <constraintErrorMessage>Vmodem success string too long (limit 40 characters)</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="modem-init-string">
      <properties>
        <help>String that is sent to the modem when a connection succeeds</help>
        <constraint>
          <regex>.{0,254}</regex>
        </constraint>
        <constraintErrorMessage>Vmodem modem init string too long (limit 254 characters)</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="auto-connect-hostport">
      <properties>
        <help>Port number the target host is listening on for messages</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Port number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="auto-connect-hostname">
      <properties>
        <help>Preconfigured target host name</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IP address of host</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of host</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>Fully qualified host name of host</description>
        </valueHelp>
        <constraint>
          <validator name="ip-address"/>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="mode">
      <properties>
        <help>Connection mode</help>
        <completionHelp>
          <list>auto manual</list>
        </completionHelp>
        <constraint>
          <regex>(auto|manual)</regex>
        </constraint>
      </properties>
      <defaultValue>auto</defaultValue>
    </leafNode>
    <leafNode name="response-delay">
      <properties>
        <help>AT Command Response Delay</help>
        <valueHelp>
          <format>u32:0-999</format>
          <description>Specifies the delay in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-999"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
    <leafNode name="send-connect-status">
      <properties>
        <help>Send connection status as</help>
        <completionHelp>
          <list>numeric verbose disable</list>
        </completionHelp>
        <constraint>
          <regex>(numeric|verbose|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>numeric</defaultValue>
    </leafNode>
    <node name="hardware-signals">
      <properties>
        <help>Hardware signals assignment</help>
      </properties>
      <children>
        <leafNode name="dtr">
          <properties>
            <help>DTR signal assignment</help>
            <completionHelp>
              <list>always-on acts-as-dcd acts-as-ri</list>
            </completionHelp>
            <constraint>
              <regex>(always-on|acts-as-dcd|acts-as-ri)</regex>
            </constraint>
          </properties>
          <defaultValue>always-on</defaultValue>
        </leafNode>
        <leafNode name="rts">
          <properties>
            <help>RTS signal assignment</help>
            <completionHelp>
              <list>always-on acts-as-dcd acts-as-ri</list>
            </completionHelp>
            <constraint>
              <regex>(always-on|acts-as-dcd|acts-as-ri)</regex>
            </constraint>
          </properties>
          <defaultValue>always-on</defaultValue>
        </leafNode>
        <leafNode name="dcd">
          <properties>
            <help>DCD signal assignment</help>
            <completionHelp>
              <list>always-on on-when-host-connect</list>
            </completionHelp>
            <constraint>
              <regex>(always-on|on-when-host-connect)</regex>
            </constraint>
          </properties>
          <defaultValue>always-on</defaultValue>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
