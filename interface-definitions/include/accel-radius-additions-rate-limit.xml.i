<!-- included start from accel-radius-additions-rate-limit.xml.i -->
<node name="rate-limit">
  <properties>
    <help>Upload/Download speed limits</help>
  </properties>
  <children>
    <leafNode name="attribute">
      <properties>
        <help>Specifies which radius attribute contains rate information. (default is Filter-Id)</help>
      </properties>
    </leafNode>
    <leafNode name="vendor">
      <properties>
        <help>Specifies the vendor dictionary. (dictionary needs to be in /usr/share/accel-ppp/radius)</help>
      </properties>
    </leafNode>
    <leafNode name="enable">
      <properties>
        <help>Enables Bandwidth shaping via RADIUS</help>
        <valueless />
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
