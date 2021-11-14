export GNUPGHOME = $(CURDIR)/gpg
SHELL = /bin/bash
include /usr/share/dpkg/architecture.mk

# List of packages to build
# for each of these, the source must be available in a directory
# $PACKAGE_$VERSION
#
# if the directory doesn't exist, but there is a directory
# overlays/$PACKAGE and a directory overlays/$PACKAGE_$VERSION,
# the contents of both directories will be copied sequentially to
# $PACKAGE_$VERSION, allowing identical data for similar packages (eg.
# multiple versions of the same packages) to be stored only once
#
# the suffix (_F, _A, _B or _S) specifies the type of build

PACKAGES = \
linux_42.0_F \
nonfree-package_0.1_F \
package_0.1_F \
package_0.1_A \
package_0.2_F \
package-built-using_0.1_F \
main-contrib-with-debug_0.1_F \
main-contrib-with-debug_0.2_F \
binnmu_0.1_F \
binnmu_0.1+b1_B \
binnmu_0.2_S \
binnmu_0.2_B \
pkgnew_0.1_AB \
pkgnew_0.1_BB \
pkgnew_0.1_F \
pkgnew_0.2~exp_F \
pkgnew_0.2_S \
pkgnew_0.2_A \
pkgnew_0.2_B \
pkgnew_0.3_F \
snowman_0.1_F \
grave_0.1_F \

OTHER = \
linux_42.0-1_source.changes \

ALL = $(PACKAGES)

stamp-all: $(ALL) $(OTHER)
	touch $@

%.orig.tar.gz:
	t=$*; \
	dir=$${t/_/-}; \
	base=$${t%_*}; \
	if [ ! -d $$dir ] ; then\
		cp -rv overlays/$$base/ ./$$dir/; \
		cp -Trv overlays/$$dir/ ./$$dir; \
	fi; \
	if [ ! -f $$t.orig.tar.gz ]; then \
		tar -czf $$t.orig.tar.gz --exclude=debian $${t/_/-}; \
	fi

%_F: %.orig.tar.gz
	p=$*; (cd $${p/_/-}; dpkg-buildpackage -F)

%_A: %.orig.tar.gz
	p=$*; (cd $${p/_/-}; dpkg-buildpackage -A)

# build packages as if they were built with
# sbuild --dpkg-file-suffix="-buildd"
%_AB: %.orig.tar.gz
	ARCH=all; \
	BUILD_OPT=A; \
	t=$*; \
	dir=$${t/_/-}; \
	p=$*; p=$${p%%_*}; \
	( \
		cd $${dir}; \
		V=`dpkg-parsechangelog -S Version`; \
		f=$${p}_$${V}_$${ARCH}; \
		dpkg-buildpackage -$${BUILD_OPT} \
		--no-sign \
		--buildinfo-option=-O../$${f}-buildd.buildinfo \
		--changes-option=-O../$${f}-buildd.changes; \
		debsign ../$${f}-buildd.changes; \
	)

%_B: %.orig.tar.gz
	p=$*; (cd $${p/_/-}; dpkg-buildpackage -B)

# build packages as if they were built with
# sbuild --dpkg-file-suffix="-buildd"
%_BB: %.orig.tar.gz
	ARCH=$(DEB_HOST_ARCH); \
	BUILD_OPT=B; \
	t=$*; \
	dir=$${t/_/-}; \
	p=$*; p=$${p%%_*}; \
	( \
		cd $${dir}; \
		V=`dpkg-parsechangelog -S Version`; \
		f=$${p}_$${V}_$${ARCH}; \
		dpkg-buildpackage -$${BUILD_OPT} \
		--no-sign \
		--buildinfo-option=-O../$${f}-buildd.buildinfo \
		--changes-option=-O../$${f}-buildd.changes; \
		debsign ../$${f}-buildd.changes; \
	)

%_S: %.orig.tar.gz
	p=$*; (cd $${p/_/-}; dpkg-buildpackage -S)

%_source.changes: %_amd64.changes
	mergechanges -S $< /dev/null > $@
	debsign --no-re-sign $@

# dummy rule, needed for the _source.changes rule
%_amd64.changes:
	true

clean:
	set -e; for j in $(ALL); do \
	  p=$${j%_*}; \
	  dir=$${p/_/-}; \
	  if [ -d overlays/$$dir ]; then rm -rf ./$$dir; \
	    else make -C $$dir -f debian/rules clean; fi; \
	done
	rm -f *.tar.gz *.tar.xz *.buildinfo *.dsc *.changes *.diff.gz *.deb
	rm -f gpg/*~
	rm -f stamp-*

.PRECIOUS: %.orig.tar.gz %_amd64.changes
