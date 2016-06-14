FROM ovn-scale-test-base

# Used to specify a specific version of OVS to build with
ARG ovs_repo=https://github.com/openvswitch/ovs.git
ARG ovs_branch=master

# Download OVS from git master
RUN git clone $ovs_repo \
    && git fetch $ovs_repo $ovs_branch \
    && git checkout FETCH_HEAD \
    && cd /ovs \
    && ./boot.sh \
    && ./configure \
    &&  make -j4 \
    &&  make install

COPY ovn-sandbox-database.sh /bin/ovn_set_database
RUN chmod 755 /bin/ovn_set_database

COPY ovn-sandbox-chassis.sh /bin/ovn_set_chassis
RUN chmod 755 /bin/ovn_set_chassis

# ENTRYPOINT ["/usr/local/bin/ovn_set_database"]
