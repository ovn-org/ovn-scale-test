FROM ovn-scale-test-base

# Download OVS from git master
RUN git clone https://github.com/openvswitch/ovs.git \
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
