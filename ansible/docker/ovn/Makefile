image_name=ovn-scale-test-ovn

ifndef ovsrepo
ovs_repo=https://github.com/openvswitch/ovs.git
else
ovs_repo=${ovsrepo}
endif
ifndef ovsbranch
ovs_branch=master
else
ovs_branch=${ovsbranch}
endif

image:
	echo "ovs_repo: ${ovs_repo} ovs_branch: ${ovs_branch}"
	${OVNSUDO} docker build --build-arg ovsrepo=${ovs_repo} --build-arg ovsbranch=${ovs_branch} --force-rm=true -t ${image_name} .
