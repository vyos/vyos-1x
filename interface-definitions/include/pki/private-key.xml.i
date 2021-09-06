<!-- include start from pki/private-key.xml.i -->
<node name="private">
  <properties>
    <help>Private key</help>
  </properties>
  <children>
    <leafNode name="key">
      <properties>
        <help>Private key in PKI configuration</help>
        <completionHelp>
          <path>pki key-pair</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Name of private key in PKI configuration</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="passphrase">
      <properties>
        <help>Private key passphrase</help>
        <valueHelp>
          <format>txt</format>
          <description>Passphrase to decrypt the private key</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
