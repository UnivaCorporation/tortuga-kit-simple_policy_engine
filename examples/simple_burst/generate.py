#!/usr/bin/env python

# Copyright 2008-2018 Univa Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generate Simple Policy Engine configuration for bursting"""


import sys
import os.path
import glob
import shutil
from tortuga.cli.tortugaCli import TortugaCli
from tortuga.config.configManager import ConfigManager
from jinja2 import Environment, FileSystemLoader, StrictUndefined

PUPPET_ROOT = '/etc/puppetlabs'


class SimplePolicyEngineSetupApp(TortugaCli):
    """Application base class for Simple Policy Engine setup script"""

    def __init__(self):
        super(SimplePolicyEngineSetupApp, self).__init__()

        self.addOption('--software-profile', metavar='NAME')
        self.addOption('--hardware-profile', metavar='NAME')
        self.addOption('--slots-per-host', type=int, default=1,
                       metavar='NUM',
                       help='Number of slots per burst host')
        self.addOption('--polling-interval', type=int, default=300,
                       metavar='NUM',
                       help='Polling interval (in seconds) (default=%default)')
        self.addOption('--burst-queue', default='burst.q', metavar='NAME',
                       help='Grid Engine queue used for burst hosts')
        self.addOption('--force', action='store_true', default=False)

    def parseArgs(self, usage=None):
        super(SimplePolicyEngineSetupApp, self).parseArgs(usage=usage)

        if not self.getArgs().software_profile or \
                not self.getArgs().hardware_profile:
            sys.stderr.write(
                'Error: --software-profile and --hardware-profile'
                ' arguments must be specified\n')

            sys.exit(1)

    def runCommand(self):
        self.parseArgs()

        self.generate_config()

    def generate_config(self):
        """Generate configuration from templates"""

        cfgmgr = ConfigManager()

        script_dir = os.path.join(cfgmgr.getRoot(), 'rules')

        if not os.path.exists(script_dir):
            print('Creating rules directory \"{0}\"'.format(script_dir))

            os.makedirs(script_dir)
        else:
            if not self.getArgs().force:
                sys.stderr.write('Script directory \"{0}\" already exists.\n'
                                 'Use --force to overwrite current'
                                 ' scripts\n'.format(script_dir))

                sys.exit(1)

            print('Overwriting any scripts in directory \"{0}\"'.format(
                script_dir))

        # Determine UGE cell directory from environment
        if not os.getenv('SGE_ROOT') or not os.getenv('SGE_CELL'):
            print('Error: UGE environment is not sourced', file=sys.stderr)

            sys.exit(1)

        cell_dir = os.path.join(os.getenv('SGE_ROOT'), os.getenv('SGE_CELL'))

        template_vars = {
            'tortuga_root': cfgmgr.getRoot(),
            'uge_cell_dir': cell_dir,
            'script_dir': script_dir,
            'burst_swprofile': self.getArgs().software_profile,
            'burst_hwprofile': self.getArgs().hardware_profile,
            'burst_queue': 'burst.q',
            'polling_interval': self.getArgs().polling_interval,
            'slots_per_host': self.getArgs().slots_per_host,
        }

        env = Environment(loader=FileSystemLoader('templates'),
                          undefined=StrictUndefined)

        for filename in glob.glob('templates/*.j2'):
#             print('Processing template {0}'.format(
#                 os.path.basename(filename)))

            template = env.get_template(os.path.basename(filename))

            dstfile = os.path.join(
                script_dir,
                os.path.splitext(os.path.basename(filename))[0])

            print('  - writing {0}'.format(os.path.basename(dstfile)))

            with open(dstfile, 'w') as outfp:
                template.stream(template_vars).dump(outfp)


def find_puppet_moduledir(module_name):
    dirname = None

    for dirpath, dirnames, _ in os.walk(
            os.path.join(PUPPET_ROOT, 'code/environments')):
        for dirname in dirnames:
            if dirname == 'tortuga_kit_uge':
                break
        else:
            continue

        break
    else:
        return None

    return os.path.join(dirpath, dirname)


if __name__ == '__main__':
    SimplePolicyEngineSetupApp().run()
