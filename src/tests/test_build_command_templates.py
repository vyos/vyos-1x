# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

script = 'scripts/build-command-templates'
schema = 'schema/interface_definition.rng'

definition = """<?xml version="1.0"?>
<interfaceDefinition>
  <node name="foo">
    <properties>
      <help>Foo</help>
    </properties>
    <children>
      <leafNode name="{name}">
        <properties>
          <help>Help of {name}</help>
        </properties>
        <defaultValue>{default}</defaultValue>
      </leafNode>
    </children>
  </node>
</interfaceDefinition>
"""


class TestBuildCommandTemplates(TestCase):
    def node_def(self, default):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'foo.xml'
            source.write_text(definition.format(name='bar', default=default))
            out = Path(tmp) / 'out'
            out.mkdir()
            subprocess.run([script, str(source), schema, str(out)], check=True)
            return (out / 'foo' / 'bar' / 'node.def').read_text()

    def test_default_in_help(self):
        self.assertIn(
            'help: Help of bar (default: 192.0.2.1)', self.node_def('192.0.2.1')
        )

    def test_default_with_percent(self):
        # the CLI prints the help with printf, "%any" would show as "0x0p+0ny"
        self.assertIn('help: Help of bar (default: %%any)', self.node_def('%any'))
