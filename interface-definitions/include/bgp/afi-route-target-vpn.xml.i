<!-- include start from bgp/route-target-both.xml.i -->
<node name="route-target">
  <properties>
    <help>Specify route target list</help>
  </properties>
  <children>
    <node name="vpn">
      <properties>
        <help>Between current address-family and VPN</help>
      </properties>
      <children>
        <leafNode name="both">
          <properties>
            <help>Route Target both import and export</help>
            <valueHelp>
              <format>txt</format>
              <description>Space separated route target list (A.B.C.D:MN|EF:OPQR|GHJK:MN)</description>
            </valueHelp>
            <constraint>
              <validator name="bgp-rd-rt" argument="--route-target-multi"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="import">
          <properties>
            <help>Route Target import</help>
            <valueHelp>
              <format>txt</format>
              <description>Space separated route target list (A.B.C.D:MN|EF:OPQR|GHJK:MN)</description>
            </valueHelp>
            <constraint>
              <validator name="bgp-rd-rt" argument="--route-target-multi"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="export">
          <properties>
            <help>Route Target export</help>
            <valueHelp>
              <format>txt</format>
              <description>Space separated route target list (A.B.C.D:MN|EF:OPQR|GHJK:MN)</description>
            </valueHelp>
            <constraint>
              <validator name="bgp-rd-rt" argument="--route-target-multi"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
