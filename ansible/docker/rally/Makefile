image_name=ovn-scale-test-rally

image:
	tar cvzf /tmp/ovn-scale-test.tgz ../../../../ovn-scale-test
	tar xvzf /tmp/ovn-scale-test.tgz
	${OVNSUDO} docker build --force-rm=true -t ${image_name} .
	rm -rf ./ovn-scale-test
