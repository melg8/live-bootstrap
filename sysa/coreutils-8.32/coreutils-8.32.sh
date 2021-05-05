# SPDX-FileCopyrightText: 2021 Melg Eight <mailto:public.melg8@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

src_prepare() {
    default_src_prepare

    # Disable generation of man pages due to lack of needed perl 5.8
    # dependency.
    cp man/dummy-man man/help2man
}

src_configure() {
    # Disable "you should not run configure as root" error from configuration
    # system of coreutils.
    export FORCE_UNSAFE_CONFIGURE=1

    # Disable installation of `expr` because it's not working (`expr` appears
    # not executable file).

    ./configure \
        --prefix="${PREFIX}" \
        --libdir="${PREFIX}/lib/musl" \
        --enable-no-install-program=expr \
        --target=i386-unknown-linux-gnu \
        --host=i386-unknown-linux-gnu \
        --build=i386-unknown-linux-gnu
}

src_compile() {
    make MAKEINFO=true DESTDIR="${DESTDIR}"
}

src_install() {
    make MAKEINFO=true DESTDIR="${DESTDIR}" install
}
