<!-- include start from static/static-route-bfd.xml.i -->
<node name="bfd">
  <properties>
    <help>BFD monitoring</help>
  </properties>
  <children>
    #include <include/bfd/profile.xml.i>
    <node name="multi-hop">
      <properties>
        <help>Use BFD multi hop session</help>
      </properties>
      <children>
       <tagNode name="source">
         <properties>
           <help>Use source for BFD session</help>
           <valueHelp>
             <format>ipv4</format>
             <description>IPv4 source</description>
           </valueHelp>
           <constraint>
             <validator name="ipv4-address"/>
           </constraint>
         </properties>
         <children>
           #include <include/bfd/profile.xml.i>
         </children>
       </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->