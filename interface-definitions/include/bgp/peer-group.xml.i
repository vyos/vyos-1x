<!-- include start from bgp/peer-group.xml.i -->
<leafNode name="peer-group">
  <properties>
    <help>Peer group for this peer</help>
    <completionHelp>
      <path>${COMP_WORDS[@]:1:${#COMP_WORDS[@]}-5} peer-group</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Peer-group name</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->
