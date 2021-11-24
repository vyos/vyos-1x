<!-- include start from accel-ppp/auth-local-users.xml.i -->
<node name="local-users">
  <properties>
    <help>Local user authentication for PPPoE server</help>
  </properties>
  <children>
    <tagNode name="username">
      <properties>
        <help>User name for authentication</help>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        <leafNode name="password">
          <properties>
            <help>Password for authentication</help>
          </properties>
        </leafNode>
        <leafNode name="static-ip">
          <properties>
            <help>Static client IP address</help>
            <constraint>
              <validator name="ipv4-address"/>
            </constraint>
          </properties>
          <defaultValue>*</defaultValue>
        </leafNode>
        <node name="rate-limit">
          <properties>
            <help>Upload/Download speed limits</help>
          </properties>
          <children>
            <leafNode name="upload">
              <properties>
                <help>Upload bandwidth limit in kbits/sec</help>
                <constraint>
                  <validator name="numeric" argument="--range 1-10000000"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="download">
              <properties>
                <help>Download bandwidth limit in kbits/sec</help>
                <constraint>
                  <validator name="numeric" argument="--range 1-10000000"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
