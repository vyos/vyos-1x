<!-- include start from accel-ppp/auth-protocols.xml.i -->
<leafNode name="protocols">
  <properties>
    <help>Authentication protocol for remote access peer</help>
    <completionHelp>
      <list>pap chap mschap mschap-v2</list>
    </completionHelp>
    <valueHelp>
      <format>pap</format>
      <description>Authentication via PAP (Password Authentication Protocol)</description>
    </valueHelp>
    <valueHelp>
      <format>chap</format>
      <description>Authentication via CHAP (Challenge Handshake Authentication Protocol)</description>
    </valueHelp>
    <valueHelp>
      <format>mschap</format>
      <description>Authentication via MS-CHAP (Microsoft Challenge Handshake Authentication Protocol)</description>
    </valueHelp>
    <valueHelp>
      <format>mschap-v2</format>
      <description>Authentication via MS-CHAPv2 (Microsoft Challenge Handshake Authentication Protocol, version 2)</description>
    </valueHelp>
    <constraint>
      <regex>(pap|chap|mschap|mschap-v2)</regex>
    </constraint>
    <multi/>
  </properties>
  <defaultValue>pap chap mschap mschap-v2</defaultValue>
</leafNode>
<!-- include end -->
