image_name=ovn-scale-test-ovn

image:
	${OVNSUDO} docker build --build-arg ovs_repo={{ ovs_repo}} --build-arg ovs_branch={{ ovs_branch }} --force-rm=true -t ${image_name} .
