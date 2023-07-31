<!-- included start from ospfv3/database.xml.i -->
<node name="database">
  <properties>
    <help>Show OSPFv3 Link state database information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <tagNode name="adv-router">
      <properties>
        <help>Search by Advertising Router ID</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt;</list>
        </completionHelp>
      </properties>
      <children>
        #include <include/ospfv3/linkstate-id.xml.i>
      </children>
    </tagNode>
    <node name="any">
      <properties>
        <help>Search by Any Link state Type</help>
      </properties>
      <children>
        <tagNode name="any">
          <properties>
            <help>Search by Link state ID</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <children>
            #include <include/frr-detail.xml.i>
            #include <include/ospfv3/dump.xml.i>
            #include <include/ospfv3/internal.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
    <tagNode name="any">
      <properties>
        <help>Search by Link state ID</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt;</list>
        </completionHelp>
      </properties>
      <command>vtysh -c "show ipv6 ospf6 database * $6"</command>
      <children>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/adv-router-id-node-tag.xml.i>
      </children>
    </tagNode>
    <node name="as-external">
      <properties>
        <help>Show AS-External LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        <tagNode name="any">
          <properties>
            <help>Search by Advertising Router ID</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>vtysh -c "show ipv6 ospf6 database as-external * $7"</command>
          <children>
            #include <include/frr-detail.xml.i>
            #include <include/ospfv3/dump.xml.i>
            #include <include/ospfv3/internal.xml.i>
          </children>
        </tagNode>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <tagNode name="as-external">
      <properties>
        <help>Search by Advertising Router IDs</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt;</list>
        </completionHelp>
      </properties>
      <children>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
        #include <include/ospfv3/adv-router-id-node-tag.xml.i>
      </children>
    </tagNode>
    #include <include/frr-detail.xml.i>
    #include <include/ospfv3/internal.xml.i>
    #include <include/ospfv3/linkstate-id.xml.i>
    #include <include/ospfv3/self-originated.xml.i>
    <node name="group-membership">
      <properties>
        <help>Show Group-Membership LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="inter-prefix">
      <properties>
        <help>Show Inter-Area-Prefix LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="inter-router">
      <properties>
        <help>Show Inter-Area-Router LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="intra-prefix">
      <properties>
        <help>Show Intra-Area-Prefix LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="link">
      <properties>
        <help>Show Link LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="network">
      <properties>
        <help>Show Network LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="node.tag">
      <properties>
        <help>Show LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="router">
      <properties>
        <help>Show router LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
    <node name="type-7">
      <properties>
        <help>Show Type-7 LSAs</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/ospfv3/adv-router.xml.i>
        #include <include/frr-detail.xml.i>
        #include <include/ospfv3/dump.xml.i>
        #include <include/ospfv3/internal.xml.i>
        #include <include/ospfv3/linkstate-id.xml.i>
        #include <include/ospfv3/linkstate-id-node-tag.xml.i>
        #include <include/ospfv3/self-originated.xml.i>
      </children>
    </node>
  </children>
</node>
<!-- included end -->
