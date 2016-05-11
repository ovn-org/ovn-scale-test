FROM ovn-scale-test-base

RUN apt-get install -y --no-install-recommends \
            build-essential \
            libssl-dev \
            libffi-dev \
            python-dev \
            libxml2-dev \
            libxslt1-dev \
            libpq-dev \
            wget \
            python-pip \
	    openssh-server \
    && apt-get clean

# Download Rally customized for OVN
RUN git clone https://github.com/huikang/rally rally_ovn_scale_test

# Install Rally customized for OVN
RUN cd rally_ovn_scale_test \
    && ./install_rally.sh

# Install OVN scale test plugin for rally
# (TODO) use master branch after the branch got merged upstream
RUN git clone https://github.com/huikang/ovn-scale-test.git
RUN cd ovn-scale-test \
    && git checkout docker-rally-ovs-create-network \
    && ./install.sh

RUN mkdir /var/run/sshd
CMD ["/usr/sbin/sshd", "-D"]
