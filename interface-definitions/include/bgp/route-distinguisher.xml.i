<!-- include start from bgp/route-distinguisher.xml.i -->
<leafNode name="rd">
  <properties>
    <help>Route Distinguisher</help>
    <valueHelp>
      <format>ASN:NN_OR_IP-ADDRESS:NN</format>
      <description>Route Distinguisher, (x.x.x.x:yyy|xxxx:yyyy)</description>
    </valueHelp>
    <constraint>
      <validator name="bgp-rd-rt" argument="--route-distinguisher"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
