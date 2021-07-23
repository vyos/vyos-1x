<!-- include start from interface/vxlan-endpoint.xml.i -->
<leafNode name="port">
  <properties>
    <help>Destination port of VXLAN tunnel (default: 8472)</help>
    <valueHelp>
    <format>u32:1-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
#include <include/interface/tunnel-remote.xml.i>
<!-- include end from interface/vxlan-endpoint.xml.i -->
