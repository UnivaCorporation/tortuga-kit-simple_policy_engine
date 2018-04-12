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

from pathlib import Path
from setuptools import find_packages, setup


setup(
    name='tortuga-simple-policy',
    version='6.3.0',
    url='http://univa.com',
    author='Univa Corporation',
    author_email='engineering@univa.com',
    license='Apache 2.0',
    packages=find_packages(exclude=['tortuga_kits']),
    namespace_packages=['tortuga'],
    zip_safe=False,
    data_files=[
        ('man/man8', [
            str(fn) for fn in Path(Path('man') / Path('man8')).iterdir()]),
    ],
    entry_points={
        'console_scripts': [
            'add-rule=tortuga.rule.scripts.add_rule:main',
            'delete-rule=tortuga.rule.scripts.delete_rule:main',
            'disable-rule=tortuga.rule.scripts.disable_rule:main',
            'enable-rule=tortuga.rule.scripts.enable_rule:main',
            'execute-rule=tortuga.rule.scripts.execute_rule:main',
            'get-rule=tortuga.rule.scripts.get_rule:main',
            'get-rule-list=tortuga.rule.scripts.get_rule_list:main',
            'post-application-data=tortuga.rule.scripts.post_application_data:main',
        ],
    },
)
