#!/bin/sh
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

blacklist_url='ftp://ftp.univ-tlse1.fr/pub/reseau/cache/squidguard_contrib/blacklists.tar.gz'
data_dir="/opt/vyatta/etc/config/url-filtering"
archive="${data_dir}/squidguard/archive"
db_dir="${data_dir}/squidguard/db"
conf_file="/etc/squidguard/squidGuard.conf"
tmp_conf_file="/tmp/sg_update_db.conf"

#$1-category
#$2-type
#$3-list
create_sg_db ()
{
       FILE=$db_dir/$1/$2
       if test -f "$FILE"; then
                rm -f ${tmp_conf_file}
                printf "dbhome $db_dir\ndest $1 {\n     $3      $1/$2\n}\nacl {\n       default {\n             pass    any\n   }\n}" >> ${tmp_conf_file}
                /usr/bin/squidGuard -b -c ${tmp_conf_file} -C $FILE
                rm -f ${tmp_conf_file}
       fi

}

while [ $# -gt 0 ]
do
    case $1 in
    --update-blacklist)
        update="yes"
        ;;
    --auto-update-blacklist)
        auto="yes"
        ;;
    --vrf)
        vrf="yes"
        ;;
    (-*) echo "$0: error - unrecognized option $1" 1>&2; exit 1;;
    (*) break;;
    esac
    shift
done

if [ ! -d ${db_dir} ]; then
    mkdir -p ${db_dir}
    getent passwd proxy 2> /dev/null
    if [ $? -ne 0 ]; then
        echo "proxy system user does not exist"
        exit 1
    fi
    getent group proxy 2> /dev/null
    if [ $? -ne 0 ]; then
        echo "proxy system group does not exist"
        exit 1
    fi
    chown proxy:proxy ${db_dir}
fi

free_space=$(expr $(df ${db_dir} | grep -v Filesystem | awk '{print $4}') \* 1024)
mb_size="100"
required_space=$(expr $mb_size \* 1024 \* 1024) # 100 MB
if [ ${free_space} -le ${required_space} ]; then
    echo "Error: not enough disk space, required  ${mb_size} MiB"
    exit 1
fi

if [[ -n $update ]] && [[ $update -eq "yes" ]]; then
    tmp_blacklists='/tmp/blacklists.gz'
    if [[ -n $vrf ]] && [[ $vrf -eq "yes" ]]; then
        sudo ip vrf exec $1 curl -o $tmp_blacklists $blacklist_url
    else
        curl -o $tmp_blacklists $blacklist_url
    fi
    if [ $? -ne 0 ]; then
        echo "Unable to download [$blacklist_url]!"
        exit 1
    fi
    echo "Uncompressing blacklist..."
    tar --directory /tmp -xf $tmp_blacklists
    if [ $? -ne 0 ]; then
        echo "Unable to uncompress [$blacklist_url]!"
    fi

    if [ ! -d ${archive} ]; then
        mkdir -p ${archive}
    fi

    rm -rf ${archive}/*
    count_before=$(find ${db_dir} -type f \( -name domains -o -name urls \) | xargs wc -l | tail -n 1 | awk '{print $1}')
    mv ${db_dir}/* ${archive} 2> /dev/null
    mv /tmp/blacklists/* ${db_dir}
    if [ $? -ne 0 ]; then
        echo "Unable to install [$blacklist_url]"
        exit 1
    fi
    mv ${archive}/local-* ${db_dir} 2> /dev/null
    rm -rf /tmp/blacklists $tmp_blacklists 2> /dev/null
    count_after=$(find ${db_dir} -type f \( -name domains -o -name urls \) | xargs wc -l | tail -n 1 | awk '{print $1}')

    # fix permissions
    chown -R proxy:proxy ${db_dir}

    #create db
    category_list=(`find $db_dir -type d -exec basename {} \; `)
    for category in ${category_list[@]}
    do
        create_sg_db $category "domains" "domainlist"
        create_sg_db $category "urls" "urllist"
        create_sg_db $category "expressions" "expressionlist"
    done
    chown -R proxy:proxy ${db_dir}
    chmod 755 ${db_dir}

    logger --priority WARNING "webproxy blacklist entries updated (${count_before}/${count_after})"

else
    echo "SquidGuard blacklist updater"
    echo ""
    echo "Usage:"
    echo "--update-blacklist            Download latest version of the SquidGuard blacklist"
    echo "--auto-update-blacklist       Automatically update"
    echo ""
    exit 1
fi

