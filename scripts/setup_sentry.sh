#!/usr/bin/env bash

# Export Folder Constant
export HOME_BUILD_SCRIPTS_REPORT_IUPDATE_FOLDER=/home/build/scripts/report.iupdate.io
export HOME_BUILD_SCRIPTS_REPORT_IUPDATE_CONF_FOLDER=$HOME_BUILD_SCRIPTS_REPORT_IUPDATE_FOLDER/conf
export HOME_SRV_REPORT_IUPDATE_FOLDER=/home/srv/projects/report.iupdate.io
export HOME_SRV_REPORT_IUPDATE_CONF_FOLDER=$HOME_SRV_REPORT_IUPDATE_FOLDER/conf
export HOME_SRV_REPORT_IUPDATE_DJANGO_LOGS_FOLDER=$HOME_SRV_REPORT_IUPDATE_FOLDER/logs

# Delete Old Source
rm -Rf $HOME_SRV_REPORT_IUPDATE_FOLDER

mkdir $HOME_SRV_REPORT_IUPDATE_FOLDER
mkdir $HOME_SRV_REPORT_IUPDATE_CONF_FOLDER
mkdir $HOME_SRV_REPORT_IUPDATE_DJANGO_LOGS_FOLDER

echo "|*********** INSTALL DEPENDENCIES *************|"
# Install Sentry dependencies
sudo yum -y install gcc clang cmake python-setuptools python-devel libxslt libxslt-devel libxslt-python libffi libffi-devel libjpeg-turbo-devel libjpeg-turbo-static libjpeg-turbo libjpeg-turbo-utils libxml2-python libxml2-static libxml2 libxml2-devel libxslt libxslt-devel libxslt-python libyaml libyaml-devel libzip libzip-devel postgresql-devel openssl-devel mariadb-devel
pip install lxml
pip install -U virtualenv
pip install MySQL-python
pip install django-redis-sessions-fork
pip install python-memcached
pip install redis hiredis nydus
pip install ujson

wget https://bootstrap.pypa.io/ez_setup.py -O - | python
rm -Rf setuptools*

echo "|*********** CLONE GITHUB SENTRY *************|"
cd $HOME_BUILD_SCRIPTS_REPORT_IUPDATE_FOLDER
git clone https://boxstore:huongduong3@github.com/boxstore/sentryserver.git
mv sentryserver $HOME_SRV_REPORT_IUPDATE_FOLDER
rm -Rf sentryserver

echo "|*********** INSTALL GITHUB SENTRY *************|"
cd $HOME_SRV_REPORT_IUPDATE_FOLDER/sentryserver
#virtualenv $HOME_SRV_REPORT_IUPDATE_FOLDER/sentryserver
#source $HOME_SRV_REPORT_IUPDATE_FOLDER/sentryserver/bin/activate
python setup.py develop

echo "|*********** SENTRY INIT CONFIG *************|"
#sentry init $HOME_SRV_REPORT_IUPDATE_CONF_FOLDER/
cp $HOME_BUILD_SCRIPTS_REPORT_IUPDATE_CONF_FOLDER/* $HOME_SRV_REPORT_IUPDATE_CONF_FOLDER/

echo "|*********** SENTRY UPGRADE DATABASE *************|"
sentry --config=$HOME_SRV_REPORT_IUPDATE_CONF_FOLDER/ upgrade
