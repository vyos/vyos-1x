#!/usr/bin/env python3

import sys

from vyos.configquery import ConfigTreeQuery
from vyos.version import get_remote_version


if __name__ == '__main__':
    image_path = ''

    config = ConfigTreeQuery()
    if config.exists('system update-check url'):
        configured_url_version = config.value('system update-check url')
        remote_url_list = get_remote_version(configured_url_version)
        if remote_url_list:
            image_path = remote_url_list[0].get('url')
        else:
            sys.exit(1)

    print(image_path)
