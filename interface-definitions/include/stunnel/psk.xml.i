<!-- include start from stunnel/psk.xml.i -->
<tagNode name="psk">
  <properties>
    <help>Pre-shared key name</help>
  </properties>
  <children>
    <leafNode name="id">
      <properties>
        <help>ID for authentication</help>
        <valueHelp>
          <format>txt</format>
          <description>ID used for authentication</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="secret">
      <properties>
        <help>pre-shared secret key</help>
        <valueHelp>
          <format>txt</format>
          <description>pre-shared secret key are required to be at least 16 bytes long, which implies at least 32 characters for hexadecimal key</description>
        </valueHelp>
        <constraint>
          <validator name="psk-secret"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
