<!-- include start from firewall/apply-path.xml.i -->
<leafNode name="apply-path">
  <properties>
    <help>Derive additional group members from another part of the configuration</help>
    <valueHelp>
      <format>txt</format>
      <description>Space-separated configuration path; a "*" segment expands every instance of the tag node at that position (e.g. "vrf name * protocols bgp neighbor")</description>
    </valueHelp>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
