<!-- included start from rip-interface.xml.i -->
<tagNode name="interface">
  <properties>
    <help>Interface name</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      <validator name="interface-name"/>
    </constraint>
  </properties>
  <children>
    <node name="authentication">
      <properties>
        <help>Authentication</help>
      </properties>
      <children>
        <tagNode name="md5">
          <properties>
            <help>MD5 key id</help>
            <valueHelp>
              <format>u32:1-255</format>
              <description>OSPF key id</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-255"/>
            </constraint>
          </properties>
          <children>
            <leafNode name="password">
              <properties>
                <help>Authentication password</help>
                <valueHelp>
                  <format>txt</format>
                  <description>MD5 Key (16 characters or less)</description>
                </valueHelp>
                <constraint>
                  <regex>^[^[:space:]]{1,16}$</regex>
                </constraint>
                <constraintErrorMessage>Password must be 16 characters or less</constraintErrorMessage>
              </properties>
            </leafNode>
          </children>
        </tagNode>
        <leafNode name="plaintext-password">
          <properties>
            <help>Plain text password</help>
            <valueHelp>
              <format>txt</format>
              <description>Plain text password (16 characters or less)</description>
            </valueHelp>
            <constraint>
              <regex>^[^[:space:]]{1,16}$</regex>
            </constraint>
            <constraintErrorMessage>Password must be 16 characters or less</constraintErrorMessage>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="split-horizon">
      <properties>
        <help>Split horizon parameters</help>
      </properties>
      <children>
        <leafNode name="disable">
          <properties>
            <help>Disable split horizon on specified interface</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="poison-reverse">
          <properties>
            <help>Disable split horizon on specified interface</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</tagNode>
<!-- included end -->
