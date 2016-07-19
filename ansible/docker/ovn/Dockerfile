FROM ovn-scale-test-base

# Used to specify a specific version of OVS to build with
ARG ovsrepo
ARG ovsbranch
ARG configflags

# Download OVS from git master
RUN echo "ovsrepo=$ovsrepo ovsbranch=$ovsbranch configflags=$configflags" \
    && git clone $ovsrepo \
    && cd /ovs \
    && git fetch $ovsrepo $ovsbranch \
    && git checkout FETCH_HEAD \
    && ./boot.sh \
    && ./configure $configflags \
    &&  make -j4 \
    &&  make install

COPY ovn-sandbox-database.sh /bin/ovn_set_database
RUN chmod 755 /bin/ovn_set_database

COPY ovn-sandbox-chassis.sh /bin/ovn_set_chassis
RUN chmod 755 /bin/ovn_set_chassis

COPY ovn-sandbox-north-ovsdb.sh /bin/ovn-sandbox-north-ovsdb.sh
COPY ovn-sandbox-south-ovsdb.sh /bin/ovn-sandbox-south-ovsdb.sh
COPY ovn-sandbox-northd.sh /bin/ovn-sandbox-northd.sh
RUN chmod 755 /bin/ovn-sandbox-north-ovsdb.sh \
              /bin/ovn-sandbox-south-ovsdb.sh \
              /bin/ovn-sandbox-northd.sh

# ENTRYPOINT ["/usr/local/bin/ovn_set_database"]
