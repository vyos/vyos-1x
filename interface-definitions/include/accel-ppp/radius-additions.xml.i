<!-- include start from accel-ppp/radius-additions.xml.i -->
<node name="radius">
  <children>
    <leafNode name="accounting-interim-interval">
      <properties>
        <help>Interval in seconds to send accounting information</help>
        <valueHelp>
          <format>u32:1-3600</format>
          <description>Interval in seconds to send accounting information</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-3600"/>
        </constraint>
        <constraintErrorMessage>Interval value must be between 1 and 3600 seconds</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="acct-interim-jitter">
      <properties>
        <help>Maximum jitter value in seconds to be applied to accounting information interval</help>
        <valueHelp>
          <format>u32:1-60</format>
          <description>Maximum jitter value in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-60"/>
        </constraint>
        <constraintErrorMessage>Jitter value must be between 1 and 60 seconds</constraintErrorMessage>
      </properties>
    </leafNode>
    <tagNode name="server">
      <children>
        <leafNode name="acct-port">
          <properties>
            <help>Accounting port</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Numeric IP port</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
          <defaultValue>1813</defaultValue>
        </leafNode>
        #include <include/accel-ppp/radius-additions-disable-accounting.xml.i>
        <leafNode name="fail-time">
          <properties>
            <help>Mark server unavailable for &lt;n&gt; seconds on failure</help>
            <valueHelp>
              <format>u32:0-600</format>
              <description>Fail time penalty</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-600"/>
            </constraint>
            <constraintErrorMessage>Fail time must be between 0 and 600 seconds</constraintErrorMessage>
          </properties>
          <defaultValue>0</defaultValue>
        </leafNode>
        #include <include/radius-priority.xml.i>
        <leafNode name="backup">
          <properties>
            <help>Use backup server if other servers are not available</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </tagNode>
    <leafNode name="timeout">
      <properties>
        <help>Timeout in seconds to wait response from RADIUS server</help>
        <valueHelp>
          <format>u32:1-60</format>
          <description>Timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-60"/>
        </constraint>
        <constraintErrorMessage>Timeout must be between 1 and 60 seconds</constraintErrorMessage>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    <leafNode name="acct-timeout">
      <properties>
        <help>Timeout for Interim-Update packets, terminate session afterwards</help>
        <valueHelp>
          <format>u32:0-60</format>
          <description>Timeout in seconds, 0 to keep active</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-60"/>
        </constraint>
        <constraintErrorMessage>Timeout must be between 0 and 60 seconds</constraintErrorMessage>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    <leafNode name="max-try">
      <properties>
        <help>Number of tries to send Access-Request/Accounting-Request queries</help>
        <valueHelp>
          <format>u32:1-20</format>
          <description>Maximum tries</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-20"/>
        </constraint>
        <constraintErrorMessage>Maximum tries must be between 1 and 20</constraintErrorMessage>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    #include <include/radius-nas-identifier.xml.i>
    #include <include/radius-nas-ip-address.xml.i>
    <leafNode name="preallocate-vif">
      <properties>
        <help>Enable attribute NAS-Port-Id in Access-Request</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="dynamic-author">
      <properties>
        <help>Dynamic Authorization Extension/Change of Authorization server</help>
      </properties>
      <children>
        <leafNode name="server">
          <properties>
            <help>IP address for Dynamic Authorization Extension server (DM/CoA)</help>
            <constraint>
              <validator name="ipv4-address"/>
            </constraint>
            <valueHelp>
              <format>ipv4</format>
              <description>IPv4 address for dynamic authorization server</description>
            </valueHelp>
          </properties>
        </leafNode>
        <leafNode name="port">
          <properties>
            <help>Port for Dynamic Authorization Extension server (DM/CoA)</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>TCP port</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
          <defaultValue>1700</defaultValue>
        </leafNode>
        <leafNode name="key">
          <properties>
            <help>Shared secret for Dynamic Authorization Extension server</help>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
