<!-- include start from interface/interface-policy.xml.i -->
<node name="policy" owner="${vyos_conf_scripts_dir}/policy-route-interface.py $VAR(../@)">
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
    <leafNode name="ipv6-route">
      <properties>
        <help>IPv6 policy route ruleset for interface</help>
        <completionHelp>
          <path>policy ipv6-route</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
