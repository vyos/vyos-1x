<!-- included start from accel-auth-local-users.xml.i -->
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
        <leafNode name="disable">
          <properties>
            <help>Option to disable a PPPoE Server user</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="password">
          <properties>
            <help>Password for authentication</help>
          </properties>
        </leafNode>
        <leafNode name="static-ip">
          <properties>
            <help>Static client IP address</help>
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
                  <validator name="numeric" argument="--range 1-65535"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="download">
              <properties>
                <help>Download bandwidth limit in kbits/sec</help>
                <constraint>
                  <validator name="numeric" argument="--range 1-65535"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </tagNode>
  </children>
</node>
<!-- included end -->
