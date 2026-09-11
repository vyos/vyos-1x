# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import importlib.util
from importlib.machinery import SourceFileLoader

def prepare_module(file_path='', module_name=''):
    """Load file_path as module_name, returning the loaded module.

    file_path may be an extensionless script (e.g. udev helpers under
    src/udev/) - spec_from_file_location() cannot infer a loader for those
    from the suffix alone, so fall back to an explicit SourceFileLoader.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        loader = SourceFileLoader(module_name, file_path)
        spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module
