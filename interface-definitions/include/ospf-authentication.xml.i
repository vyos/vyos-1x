<!-- included start from ospf-authentication.xml.i -->
<node name="authentication">
  <properties>
    <help>Authentication</help>
  </properties>
  <children>
    <node name="md5">
      <properties>
        <help>MD5 key id</help>
      </properties>
      <children>
        <tagNode name="key-id">
          <properties>
            <help>MD5 key id</help>
            <valueHelp>
              <format>u32:1-255</format>
              <description>MD5 key id</description>
            </valueHelp>
          </properties>
          <children>
            <leafNode name="md5-key">
              <properties>
                <help>MD5 authentication type</help>
                <valueHelp>
                  <format>txt</format>
                  <description>MD5 Key (16 characters or less)</description>
                </valueHelp>
              </properties>
            </leafNode>
          </children>
        </tagNode>
      </children>
    </node>
    <leafNode name="plaintext-password">
      <properties>
        <help>Plain text password</help>
        <valueHelp>
          <format>txt</format>
          <description>Plain text password (8 characters or less)</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
