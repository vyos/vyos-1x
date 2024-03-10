<!-- include start from firewall/conntrack-helper.xml.i -->
<leafNode name="conntrack-helper">
  <properties>
    <help>Match related traffic from conntrack helpers</help>
    <completionHelp>
      <list>ftp h323 pptp nfs sip tftp sqlnet</list>
    </completionHelp>
    <valueHelp>
      <format>ftp</format>
      <description>Related traffic from FTP helper</description>
    </valueHelp>
    <valueHelp>
      <format>h323</format>
      <description>Related traffic from H.323 helper</description>
    </valueHelp>
    <valueHelp>
      <format>pptp</format>
      <description>Related traffic from PPTP helper</description>
    </valueHelp>
    <valueHelp>
      <format>nfs</format>
      <description>Related traffic from NFS helper</description>
    </valueHelp>
    <valueHelp>
      <format>rtsp</format>
      <description>Related traffic from RTSP helper</description>
    </valueHelp>
    <valueHelp>
      <format>sip</format>
      <description>Related traffic from SIP helper</description>
    </valueHelp>
    <valueHelp>
      <format>tftp</format>
      <description>Related traffic from TFTP helper</description>
    </valueHelp>
    <valueHelp>
      <format>sqlnet</format>
      <description>Related traffic from SQLNet helper</description>
    </valueHelp>
    <constraint>
      <regex>(ftp|h323|pptp|nfs|rtsp|sip|tftp|sqlnet)</regex>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
