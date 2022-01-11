<!-- include start from interface/interface-policy-vif-c.xml.i -->
<node name="policy" owner="${vyos_conf_scripts_dir}/policy-route-interface.py $VAR(../../../@).$VAR(../../@).$VAR(../@)">
  <properties>
    <priority>620</priority>
    <help>Policy route options</help>
  </properties>
  <children>
    <leafNode name="route">
      <properties>
        <help>IPv4 policy route ruleset for interface</help>
        <completionHelp>
          <path>policy route</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="route6">
      <properties>
        <help>IPv6 policy route ruleset for interface</help>
        <completionHelp>
          <path>policy route6</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
