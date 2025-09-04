<!-- include start from serial/general/port-buffering.xml.i -->
<node name="port-buffering">
  <properties>
    <help>Port buffering setting</help>
  </properties>
  <children>
    <node name="local">
      <properties>
        <help>Enable local port buffering</help>
      </properties>
      <children>
        <leafNode name="view-string">
          <properties>
            <help>Local port buffering escape view string, must start with '~~'</help>
            <constraint>
              <regex>.{0,8}</regex>
            </constraint>
            <constraintErrorMessage>View string too long (limit 8 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="nfs">
      <properties>
        <help>Enable nfs port buffering</help>
      </properties>
      <children>
        <leafNode name="hostname">
          <properties>
            <help>NFS host name</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IP address of NFS host</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address of NFS host</description>
            </valueHelp>
            <valueHelp>
              <format>hostname</format>
              <description>Fully qualified host name of NFS host</description>
            </valueHelp>
            <constraint>
              <validator name="ip-address"/>
              <validator name="fqdn"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="directory">
          <properties>
            <help>Path to file</help>
            <constraint>
              <regex>.{0,40}</regex>
            </constraint>
            <constraintErrorMessage>Path string too long (limit 40 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="syslog">
      <properties>
        <help>Enable including serial message in syslog local and remote</help>
      </properties>
      <children>
        <leafNode name="level">
          <properties>
            <help>syslog marked with configured level</help>
            <completionHelp>
              <list>emergency alert critical error warning notice info debug</list>
            </completionHelp>
            <constraint>
              <regex>(emergency|alert|critical|error|warning|notice|info|debug)</regex>
            </constraint>
          </properties>
          <defaultValue>info</defaultValue>
        </leafNode>
      </children>
    </node>
    <leafNode name="add-timestamp">
      <properties>
        <help>Enable add timestamp to buffering log</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="keystroke-buffering">
      <properties>
        <help>Enable log transfer data, default is to log receive data only</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
