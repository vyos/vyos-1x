<!-- include start from static/static-route-segments.xml.i -->
<leafNode name="segments">
    <properties>
      <help>SRv6 segments</help>
      <valueHelp>
        <format>txt</format>
        <description>Segs (SIDs)</description>
      </valueHelp>
      <constraint>
        <validator name="ipv6-srv6-segments"/>
      </constraint>
    </properties>
  </leafNode>
  <!-- include end -->
