<!-- include start from serial/service/utils/tls-common.xml.i -->
<leafNode name="disable">
  <properties>
    <help>Disables TLS</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="certificate">
  <properties>
    <help>Certificate</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_pki_with_tpm.py --selector cert</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Certificate name</description>
    </valueHelp>
  </properties>
</leafNode>
<leafNode name="passphrase">
  <properties>
    <help>Private key passphrase</help>
    <constraint>
      <regex>.{0,16}</regex>
    </constraint>
    <valueHelp>
      <format>txt</format>
      <description>Passphrase to decrypt the private key</description>
    </valueHelp>
  </properties>
</leafNode>
<leafNode name="version">
  <properties>
    <help>TLS version</help>
    <completionHelp>
      <list>any tlsv1.2 tlsv1.2b tlsv1.3</list>
    </completionHelp>
    <constraint>
      <regex>(any|tlsv1.2|tlsv1.2b|tlsv1.3)</regex>
    </constraint>
  </properties>
  <defaultValue>any</defaultValue>
</leafNode>
<leafNode name="role">
  <properties>
    <help>TLS role</help>
    <completionHelp>
      <list>client server</list>
    </completionHelp>
    <constraint>
      <regex>(client|server)</regex>
    </constraint>
  </properties>
  <defaultValue>client</defaultValue>
</leafNode>
<node name="peer-verification">
  <properties>
    <help>Verification of peer certificate</help>
  </properties>
  <children>
    <leafNode name="disable">
      <properties>
        <help>Disables Peer Verification</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="country">
      <properties>
        <help>Country</help>
        <valueHelp>
          <format>txt</format>
          <description>Country</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="state">
      <properties>
        <help>state</help>
        <valueHelp>
          <format>txt</format>
          <description>state</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="locality">
      <properties>
        <help>locality</help>
        <valueHelp>
          <format>txt</format>
          <description>locality</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="organization">
      <properties>
        <help>organization</help>
        <valueHelp>
          <format>txt</format>
          <description>organization</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="organization-unit">
      <properties>
        <help>organization unit</help>
        <valueHelp>
          <format>txt</format>
          <description>organization unit</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="common-name">
      <properties>
        <help>common name</help>
        <valueHelp>
          <format>txt</format>
          <description>common name</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="email">
      <properties>
        <help>email</help>
        <valueHelp>
          <format>txt</format>
          <description>email</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<tagNode name="cipher-options">
  <properties>
    <help>Cipher option</help>
    <valueHelp>
      <format>u32:1-5</format>
      <description>Cipher (1-5)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-5"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="encryption">
      <properties>
        <help>Cipher encryption</help>
        <completionHelp>
          <list>any aes aes-gcm</list>
        </completionHelp>
        <constraint>
          <regex>(any|aes|aes-gcm)</regex>
        </constraint>
      </properties>
      <defaultValue>any</defaultValue>
    </leafNode>
    <leafNode name="min-key-size">
      <properties>
        <help>Cipher min key size</help>
        <completionHelp>
          <list>40 56 64 128 168 256</list>
        </completionHelp>
        <constraint>
          <regex>(40|56|64|128|168|256)</regex>
        </constraint>
      </properties>
      <defaultValue>40</defaultValue>
    </leafNode>
    <leafNode name="max-key-size">
      <properties>
        <help>Cipher max key size</help>
        <completionHelp>
          <list>40 56 64 128 168 256</list>
        </completionHelp>
        <constraint>
          <regex>(40|56|64|128|168|256)</regex>
        </constraint>
      </properties>
      <defaultValue>256</defaultValue>
    </leafNode>
    <leafNode name="key-exchange">
      <properties>
        <help>Cipher key exchange</help>
        <completionHelp>
          <list>any rsa edh-rsa edh-dss adh ecdh-ecdsa</list>
        </completionHelp>
        <constraint>
          <regex>(any|rsa|edh-rsa|edh-dss|adh|ecdh-ecdsa)</regex>
        </constraint>
      </properties>
      <defaultValue>any</defaultValue>
    </leafNode>
    <leafNode name="hmac">
      <properties>
        <help>Cipher hash message authentication code</help>
        <completionHelp>
          <list>any sha1 md5 sha256 sha384</list>
        </completionHelp>
        <constraint>
          <regex>(any|sha1|md5|sha256|sha384)</regex>
        </constraint>
      </properties>
      <defaultValue>any</defaultValue>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
