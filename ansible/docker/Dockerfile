FROM ubuntu:latest
# This will prevent questions from being asked during the install
ENV DEBIAN_FRONTEND noninteractive

COPY sources.list /etc/apt/

RUN apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 199369E5404BD5FC7D2FE43BCBCB082A1BB943DB \
    && apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 391A9AA2147192839E9DB0315EDB1B62EC4926EA \
    && apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 430BDF5C56E7C94E848EE60C1C4CBDCDCD2EFD2A \
    && apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 08B73419AC32B4E966C1A330E84AC2C0460F3994 \
    && apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 46095ACC8548582C1A2699A9D27D666CD88E42B4 \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python \
        python-jinja2 \
        python-kazoo \
        python-six \
        curl \
    && apt-get clean \
    && sed -i "s|'purelib': '\$base/local/lib/python\$py_version_short/dist-packages',|'purelib': '\$base/lib/python\$py_version_short/dist-packages',|;s|'platlib': '\$platbase/local/lib/python\$py_version_short/dist-packages',|'platlib': '\$platbase/lib/python\$py_version_short/dist-packages',|;s|'headers': '\$base/local/include/python\$py_version_short/\$dist_name',|'headers': '\$base/include/python\$py_version_short/\$dist_name',|;s|'scripts': '\$base/local/bin',|'scripts': '\$base/bin',|;s|'data'   : '\$base/local',|'data'   : '\$base',|" /usr/lib/python2.7/distutils/command/install.py \
    && rm -rf /usr/lib/python2.7/site-packages \
    && ln -s dist-packages /usr/lib/python2.7/site-packages

RUN apt-get install -y --no-install-recommends openvswitch-switch \
    && apt-get clean

RUN apt-get install -y --no-install-recommends ovn-central \
        ovn-host \
	ovn-docker \
	ovn-common \
    && apt-get clean

COPY ovn-sandbox-database.sh /bin/ovn_set_database
RUN chmod 755 /bin/ovn_set_database

COPY ovn-sandbox-chassis.sh /bin/ovn_set_chassis
RUN chmod 755 /bin/ovn_set_chassis

# ENTRYPOINT ["/usr/local/bin/ovn_set_database"]
