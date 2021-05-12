# SPDX-FileCopyrightText: 2021 Melg Eight <public.melg8@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Original source code for this resides in gl subfolder inside coreutils,
# but tar.gz archive have no such directory. We restore this files so that
# gnulib-tool can correctly regenerate files and apply changes from gl folder.
restore_gl_folder_in_coreutils() {
  MODULES=(
        'buffer-lcm'
        'cl-strtod'
        'cl-strtold'
        'fadvise'
        'fd-reopen'
        'heap'
        'mbsalign'
        'randint'
        'randperm'
        'randread'
        'root-dev-ino'
        'smack'
        'strnumcmp'
        'xdectoint'
        'xfts'
    )

    mkdir -p gl/lib

    for module in "${MODULES[@]}"; do
        mv lib/"${module}"* gl/lib/
    done

    ADDITIONAL_FILES=(
        'rand-isaac.h'
        'rand-isaac.c'
        'strintcmp.c'
        'xdectoimax.c'
        'xdectoumax.c'
    )
    for file in "${ADDITIONAL_FILES[@]}"; do
        mv lib/"${file}" gl/lib/
    done

    mkdir -p gl/modules
    for module in "${MODULES[@]}"; do
        mv "${module}" gl/modules/
    done

    mv tempname.c.diff gl/lib/
    mv tempname.h.diff gl/lib/
    mv tempname.diff gl/modules/
}

# Removing pre-generated files from source code, we will re-generate them.
remove_generated_configs() {
    find . -name '*.info' -delete
    find . -name '*.gmo' -delete

    rm lib/parse-datetime.c
    rm lib/gnulib.mk
    rm lib/config.hin
    rm m4/gnulib-comp.m4
    rm m4/cu-progs.m4
    rm src/cu-progs.mk
    rm src/single-binary.mk
    rm gnulib-tests/gnulib.mk
    rm Makefile.in
}

regenerate_configs() {
    build-aux/gen-lists-of-programs.sh --autoconf > m4/cu-progs.m4
    build-aux/gen-lists-of-programs.sh --automake > src/cu-progs.mk
    build-aux/gen-single-binary.sh src/local.mk > src/single-binary.mk

    restore_gl_folder_in_coreutils
    . ../../import-gnulib.sh

    # Disable generation of man pages due to lack of needed perl 5.8
    # dependency.
    cp man/dummy-man man/help2man

    # We don't have autopoint from gettext yet.
    AUTOPOINT=true autoreconf-2.69 -fi
}

src_prepare() {
    default
    remove_generated_configs
    regenerate_configs
}

src_configure() {
    # FORCE_UNSAFE_CONFIGURE disables "you should not run configure as root"
    # error from configuration system of coreutils.
    FORCE_UNSAFE_CONFIGURE=1 ./configure CFLAGS="-static -O2" \
        --prefix="${PREFIX}" \
        --disable-nls \
        --target=i386-unknown-linux-gnu \
        --host=i386-unknown-linux-gnu \
        --build=i386-unknown-linux-gnu
}

src_compile() {
     make PREFIX="${PREFIX}" MAKEINFO="true"
}

src_install() {
     make install PREFIX="${PREFIX}" MAKEINFO="true" DESTDIR="${DESTDIR}"
}
