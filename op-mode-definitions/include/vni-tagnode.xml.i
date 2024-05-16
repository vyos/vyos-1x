<!-- included start from vni-tagnode.xml.i -->
<tagNode name="vni">
  <properties>
    <help>VXLAN network identifier (VNI) number</help>
    <completionHelp>
      <list>&lt;1-16777215&gt;</list>
      <script>${vyos_completion_dir}/list_vni.sh</script>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/evpn.py show_evpn --command "$*"</command>
</tagNode>
<!-- included end -->
