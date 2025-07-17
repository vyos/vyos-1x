<!-- included start from ospf-common.xml.i -->
<leafNode name="border-routers">
  <properties>
    <help>Show IPv4 OSPF border-routers information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<node name="database">
  <properties>
    <help>Show IPv4 OSPF database information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <node name="asbr-summary">
      <properties>
        <help>Show IPv4 OSPF ASBR summary database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF ASBR summary database information of given address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF ASBR summary database of given address for given advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show summary of self-originate IPv4 OSPF ASBR database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF ASBR summary database for given address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <node name="external">
      <properties>
        <help>Show IPv4 OSPF external database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF external database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF external database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF external database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF external database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <leafNode name="max-age">
      <properties>
        <help>Show IPv4 OSPF max-age database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <node name="network">
      <properties>
        <help>Show IPv4 OSPF network database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF network database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF network database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF network database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF network database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <node name="nssa-external">
      <properties>
        <help>Show IPv4 OSPF NSSA external database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF NSSA external database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF NSSA external database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF NSSA external database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF NSSA external database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <node name="opaque-area">
      <properties>
        <help>Show IPv4 OSPF opaque-area database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF opaque-area database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF opaque-area database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF opaque-area database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF opaque-area database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <node name="opaque-as">
      <properties>
        <help>Show IPv4 OSPF opaque-as database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF opaque-as database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF opaque-as database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF opaque-as database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF opaque-as database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <node name="opaque-link">
      <properties>
        <help>Show IPv4 OSPF opaque-link database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF opaque-link database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF opaque-link database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF opaque-link database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF opaque-link database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <node name="router">
      <properties>
        <help>Show IPv4 OSPF router database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF router database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF router database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF router database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF router database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
    <leafNode name="self-originate">
      <properties>
        <help>Show IPv4 OSPF self-originate database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <node name="summary">
      <properties>
        <help>Show summary of IPv4 OSPF database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show IPv4 OSPF summary database information of specified IP address</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <tagNode name="adv-router">
              <properties>
                <help>Show IPv4 OSPF summary database of specified IP address for specified advertised router</help>
                <completionHelp>
                 <list>&lt;x.x.x.x&gt;</list>
                </completionHelp>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </tagNode>
            <leafNode name="self-originate">
              <properties>
                <help>Show self-originate IPv4 OSPF summary database</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </virtualTagNode>
        <tagNode name="adv-router">
          <properties>
            <help>Show IPv4 OSPF summary database for specified IP address of advertised router</help>
            <completionHelp>
             <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
      </children>
    </node>
  </children>
</node>
#include <include/ospf/graceful-restart.xml.i>
<tagNode name="interface">
  <properties>
    <help>Show information about specific interface</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
  </properties>
  <standalone>
    <help>Show IPv4 OSPF interface information</help>
    <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  </standalone>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<node name="mpls">
  <properties>
    <help>Show MPLS information</help>
  </properties>
  <children>
  #include <include/ldp-sync.xml.i>
  </children>
</node>
<node name="neighbor">
  <properties>
    <help>Show IPv4 OSPF neighbor information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <virtualTagNode>
      <properties>
        <help>Show IPv4 OSPF neighbor information for specified IP address or interface</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt;</list>
          <script>${vyos_completion_dir}/list_interfaces</script>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </virtualTagNode>
    #include <include/frr-detail.xml.i>
  </children>
</node>
<node name="route">
  <properties>
    <help>Show IPv4 OSPF route information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <leafNode name="detail">
      <properties>
        <help>Show detailed IPv4 OSPF route information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</node>
<!-- included end -->
