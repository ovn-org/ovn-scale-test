ifneq (,$(findstring yes,$(NO_RALLY)))
	SUBDIRS = base ovn
else
	SUBDIRS = base ovn rally
endif

subdirs:
	for dir in $(SUBDIRS); do \
		$(MAKE) -C $$dir; \
	done
