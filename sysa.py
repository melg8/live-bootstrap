#!/usr/bin/env python3
"""System A"""
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 Andrius Štikonas <andrius@stikonas.eu>
# SPDX-FileCopyrightText: 2021 Melg Eight <public.melg8@gmail.com>

import hashlib
import os
from distutils.dir_util import copy_tree
import shutil

import requests

from lib.utils import mount, umount, copytree, get_target


class SysA:
    """
    Class responsible for preparing sources for System A.
    """
    def __init__(self, arch, preserve_tmp, tmpdir):
        self.git_dir = os.path.dirname(os.path.join(__file__))
        self.arch = arch
        self.preserve_tmp = preserve_tmp

        if tmpdir is None:
            self.tmp_dir = os.path.join(self.git_dir, 'sysa', 'tmp')
        else:
            self.tmp_dir = tmpdir
        self.sysa_dir = os.path.join(self.git_dir, 'sysa')
        self.after_dir = os.path.join(self.tmp_dir, 'after')

        self.prepare()

    def __del__(self):
        if not self.preserve_tmp:
            print("Unmounting tmpfs from %s" % (self.tmp_dir))
            umount(self.tmp_dir)
            os.rmdir(self.tmp_dir)

    def check_file(self, file_name):
        """Check hash of downloaded source file."""
        checksum_store = os.path.join(self.git_dir, 'SHA256SUMS.sources')
        with open(checksum_store) as checksum_file:
            hashes = checksum_file.read().splitlines()
        for hash_line in hashes:
            if os.path.basename(file_name) in hash_line:
                # Hash is in store, check it
                expected_hash = hash_line.split()[0]

                with open(file_name, "rb") as downloaded_file:
                    downloaded_content = downloaded_file.read() # read entire file as bytes
                readable_hash = hashlib.sha256(downloaded_content).hexdigest()
                if expected_hash == readable_hash:
                    return
                raise Exception("Checksum mismatch")

        raise Exception("File checksum is not yet recorded")

    def download_file(self, url, file_name=None):
        """
        Download a single source archive.
        """
        cache_dir = os.path.join(self.git_dir, 'sources')

        # Automatically determine file name based on URL.
        if file_name is None:
            file_name = os.path.basename(url)
        abs_file_name = os.path.join(cache_dir, file_name)

        # Create a cache directory for downloaded sources
        if not os.path.isdir(cache_dir):
            os.mkdir(cache_dir)

        # Actually download the file
        if not os.path.isfile(abs_file_name):
            print("Downloading: %s" % (file_name))
            request = requests.get(url, allow_redirects=True)
            open(abs_file_name, 'wb').write(request.content)

        # Check SHA256 hash
        self.check_file(abs_file_name)
        return abs_file_name

    def get_file(self, url, mkbuild=False, output=None):
        """
        Download and prepare source packages

        url can be either:
          1. a single URL
          2. list of URLs to download. In this case the first URL is the primary URL
             from which we derive the name of package directory
        output can be used to override file name of the downloaded file(s).

        mkbuild=True can be used to pre-create build directories before
        mkdir is available.
        """
        # Single URL
        if isinstance(url, str):
            assert output is None or isinstance(output, str)
            file_name = url if output is None else output
            urls = [url]
            outputs = [output]
        # Multiple URLs
        elif isinstance(url, list):
            assert output is None or len(output) == len(url)
            file_name = url[0] if output is None else output[0]
            urls = url
            outputs = output if output is not None else [None] * len(url)
        else:
            raise TypeError("url must be either a string or a list of strings")

        # Determine installation directory
        target_name = get_target(file_name)
        target_src_dir = os.path.join(self.after_dir, target_name, 'src')

        # Install base files
        src_tree = os.path.join(self.sysa_dir, target_name)
        copytree(src_tree, self.after_dir)
        if not os.path.isdir(target_src_dir):
            os.mkdir(target_src_dir)

        for i, _ in enumerate(urls):
            # Download files into cache directory
            tarball = self.download_file(urls[i], outputs[i])

            # Install sources into target directory
            shutil.copy2(tarball, target_src_dir)

        if mkbuild:
            os.mkdir(os.path.join(self.after_dir, target_name, 'build'))

    def prepare(self):
        """
        Prepare directory structure for System A.
        We create an empty tmpfs, unpack stage0-posix.
        Rest of the files are unpacked into more structured directory /after
        """
        if not os.path.isdir(self.tmp_dir):
            os.mkdir(self.tmp_dir)
        print("Mounting tmpfs on %s" % (self.tmp_dir))
        mount('tmpfs', self.tmp_dir, 'tmpfs', 'size=8G')

        self.stage0_posix()
        self.after()

    def stage0_posix(self):
        """Copy in all the stage0-posix (formerly known as mescc-tools-seed)"""
        mescc_tools_seed_base_dir = os.path.join(self.sysa_dir, 'mescc-tools-seed',
                                                 'src', 'mescc-tools-seed')
        mescc_tools_seed_dir = os.path.join(mescc_tools_seed_base_dir, self.arch)
        copy_tree(mescc_tools_seed_dir, self.tmp_dir)

        m2_planet_dir = os.path.join(mescc_tools_seed_base_dir, 'M2-Planet')
        copytree(m2_planet_dir, self.tmp_dir)

        # At the moment not useful for bootstrap but easier to keep it
        mes_m2_dir = os.path.join(mescc_tools_seed_base_dir, 'mes-m2')
        copytree(mes_m2_dir, self.tmp_dir)

        mescc_tools_patched_dir = os.path.join(self.sysa_dir, 'mescc-tools-seed',
                                               'src', 'mescc-tools-patched')
        shutil.copytree(mescc_tools_patched_dir,
                        os.path.join(self.tmp_dir, 'mescc-tools'), shutil.ignore_patterns('*.git*'))

        # bootstrap seeds
        bootstrap_seeds_dir = os.path.join(self.sysa_dir, 'bootstrap-seeds')
        copytree(bootstrap_seeds_dir, self.tmp_dir)
        kaem_optional_seed = os.path.join(bootstrap_seeds_dir, 'POSIX',
                                          self.arch, 'kaem-optional-seed')
        shutil.copy2(kaem_optional_seed, os.path.join(self.tmp_dir, 'init'))

        # replace the init kaem with our own custom one
        shutil.move(os.path.join(self.tmp_dir, 'kaem.run'),
                    os.path.join(self.tmp_dir, 'mescc-tools-seed.kaem.run'))
        shutil.copy2(os.path.join(self.sysa_dir, 'base.kaem.run'),
                     os.path.join(self.tmp_dir, 'kaem.run'))

        # create directories needed
        os.mkdir(os.path.join(self.tmp_dir, 'bin'))

    def after(self):
        """
        Prepare sources in /after directory.
        After mescc-tools-seed we get into our own directory because
        the mescc-tools-seed one is hella messy.
        """

        self.create_after_dirs()
        self.mescc_tools_checksum()
        self.deploy_extra_files()
        self.mescc_tools_extra()
        self.mes()
        self.tcc_0_9_26()
        self.get_packages()

    def create_after_dirs(self):
        """
        Create some empty directories for early bootstrap
        This list can be eventually reduced if we include a small
        mkdir implementation written for M2-Planet.
        """
        bin_dir = os.path.join(self.after_dir, 'bin')
        lib_dir = os.path.join(self.after_dir, 'lib')
        include_dir = os.path.join(self.after_dir, 'include')

        os.mkdir(self.after_dir)
        os.mkdir(bin_dir)
        os.mkdir(lib_dir)
        os.mkdir(include_dir)
        os.mkdir(os.path.join(lib_dir, self.arch+'-mes'))
        os.mkdir(os.path.join(lib_dir, 'tcc'))
        os.mkdir(os.path.join(lib_dir, 'linux'))
        os.mkdir(os.path.join(lib_dir, 'linux', self.arch+'-mes'))
        os.mkdir(os.path.join(include_dir, 'mes'))
        os.mkdir(os.path.join(include_dir, 'gnu'))
        os.mkdir(os.path.join(include_dir, 'linux'))
        os.mkdir(os.path.join(include_dir, 'linux', self.arch))
        os.mkdir(os.path.join(include_dir, 'sys'))
        os.mkdir(os.path.join(include_dir, 'mach'))

        # Needed for patch to work, although can be fixed with TMPDIR
        os.mkdir(os.path.join(self.tmp_dir, 'tmp'))

    def mescc_tools_checksum(self):
        """Early fletcher16 checksum files"""
        shutil.copy2(os.path.join(self.sysa_dir, 'mescc-tools-seed', 'checksums'),
                     os.path.join(self.after_dir, 'mescc-tools-seed-checksums'))

    def deploy_extra_files(self):
        """Deploy misc files"""
        extra_files = ['helpers.sh', 'run.sh', 'run2.sh', 'pre-sha.sha256sums']
        for extra_file in extra_files:
            shutil.copy2(os.path.join(self.sysa_dir, extra_file), self.after_dir)

        shutil.copy2(os.path.join(self.sysa_dir, 'after.kaem'), self.tmp_dir)
        shutil.copy2(os.path.join(self.sysa_dir, 'after.kaem.run'),
                     os.path.join(self.after_dir, 'kaem.run'))
        shutil.copy2(os.path.join(self.git_dir, 'SHA256SUMS.sources'), self.after_dir)

    def mescc_tools_extra(self):
        """Some additional tools such as cp and chmod (for M2-Planet)"""
        copytree(os.path.join(self.sysa_dir, 'mescc-tools-extra'), self.after_dir)

    def mes(self):
        """GNU Mes"""
        copytree(os.path.join(self.sysa_dir, 'mes'), self.after_dir)
        mes_dir = os.path.join(self.after_dir, 'mes', 'src', 'mes')
        os.mkdir(os.path.join(mes_dir, 'bin'))
        os.mkdir(os.path.join(mes_dir, 'm2'))

    def tcc_0_9_26(self):
        """TinyCC 0.9.26 (patched by janneke)"""
        copytree(os.path.join(self.sysa_dir, 'tcc-0.9.26'), self.after_dir)

    # pylint: disable=line-too-long,too-many-statements
    def get_packages(self):
        """Prepare remaining sources"""
        # untar from libarchive 3.4
        self.get_file("https://raw.githubusercontent.com/libarchive/libarchive/3.4/contrib/untar.c")

        # gzip 1.2.4
        self.get_file("https://mirrors.kernel.org/gnu/gzip/gzip-1.2.4.tar", mkbuild=True)

        # tar 1.12
        self.get_file("https://mirrors.kernel.org/gnu/tar/tar-1.12.tar.gz", mkbuild=True)

        # sed 4.0.9
        self.get_file("https://mirrors.kernel.org/gnu/sed/sed-4.0.9.tar.gz", mkbuild=True)

        # patch 2.5.9
        self.get_file("https://ftp.gnu.org/pub/gnu/patch/patch-2.5.9.tar.gz", mkbuild=True)

        # sha-2 61555d
        self.get_file("https://github.com/amosnier/sha-2/archive/61555d.tar.gz", mkbuild=True,
                      output="sha-2-61555d.tar.gz")

        # make 3.80
        self.get_file("https://mirrors.kernel.org/gnu/make/make-3.80.tar.gz", mkbuild=True)

        # bzip2 1.0.8
        self.get_file("https://sourceware.org/pub/bzip2/bzip2-1.0.8.tar.gz", mkbuild=True)

        # tcc 0.9.27
        self.get_file("https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27.tar.bz2", mkbuild=True)

        # coreutils 5.0
        self.get_file("https://mirrors.kernel.org/gnu/coreutils/coreutils-5.0.tar.bz2", mkbuild=True)

        # heirloom-devtools
        self.get_file("http://downloads.sourceforge.net/project/heirloom/heirloom-devtools/070527/heirloom-devtools-070527.tar.bz2")

        # bash 2.05b
        self.get_file("https://ftp.gnu.org/pub/gnu/bash/bash-2.05b.tar.gz")

        # flex 2.5.11
        self.get_file("http://download.nust.na/pub2/openpkg1/sources/DST/flex/flex-2.5.11.tar.gz")

        # mes 0.23 (meslibc)
        self.get_file("https://mirrors.kernel.org/gnu/mes/mes-0.23.tar.gz")

        # musl 1.1.24
        self.get_file("https://musl.libc.org/releases/musl-1.1.24.tar.gz")

        # m4 1.4.7
        self.get_file("https://mirrors.kernel.org/gnu/m4/m4-1.4.7.tar.gz")

        # flex 2.6.4
        self.get_file("https://github.com/westes/flex/releases/download/v2.6.4/flex-2.6.4.tar.gz")

        # bison 3.4.1
        self.get_file("https://mirrors.kernel.org/gnu/bison/bison-3.4.1.tar.gz")

        # grep 2.4
        self.get_file("https://mirrors.kernel.org/gnu/grep/grep-2.4.tar.gz")

        # diffutils 2.7
        self.get_file("https://mirrors.kernel.org/gnu/diffutils/diffutils-2.7.tar.gz")

        # coreutils 6.10
        self.get_file("https://mirrors.kernel.org/gnu/coreutils/coreutils-6.10.tar.gz")

        # gawk 3.0.4
        self.get_file("https://mirrors.kernel.org/gnu/gawk/gawk-3.0.4.tar.gz")

        # perl 5.000
        self.get_file("https://github.com/Perl/perl5/archive/perl-5.000.tar.gz")

        # perl 5.003
        self.get_file("https://github.com/Perl/perl5/archive/perl-5.003.tar.gz")

        # perl 5.004_05
        self.get_file("https://www.cpan.org/src/5.0/perl5.004_05.tar.gz")

        # perl 5.005_03
        self.get_file("https://www.cpan.org/src/5.0/perl5.005_03.tar.gz")

        # perl 5.6.2
        self.get_file("https://www.cpan.org/src/5.0/perl-5.6.2.tar.gz")

        # autoconf 2.52
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.52.tar.bz2")

        # automake 1.6.3
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.6.3.tar.bz2")

        # automake 1.4-p6
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.4-p6.tar.gz")

        # autoconf 2.13
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.13.tar.gz")

        # autoconf 2.12
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.12.tar.gz")

        # libtool 1.4
        self.get_file("https://mirrors.kernel.org/gnu/libtool/libtool-1.4.tar.gz")

        # binutils 2.14
        self.get_file("https://mirrors.kernel.org/gnu/binutils/binutils-2.14.tar.bz2")

        # autoconf 2.53
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.53.tar.bz2")

        # automake 1.7
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.7.tar.bz2")

        # autoconf 2.54
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.54.tar.bz2")

        # autoconf 2.55
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.55.tar.bz2")

        # automake 1.7.8
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.7.8.tar.bz2")

        # autoconf 2.57
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.57.tar.bz2")

        # autoconf 2.59
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.59.tar.bz2")

        # automake 1.8.5
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.8.5.tar.bz2")

        # help2man 1.36.4
        self.get_file("https://mirrors.kernel.org/gnu/help2man/help2man-1.36.4.tar.gz")

        # autoconf 2.61
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.61.tar.bz2")

        # automake 1.9.6
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.9.6.tar.bz2")

        # findutils 4.2.33
        self.get_file(["https://mirrors.kernel.org/gnu/findutils/findutils-4.2.33.tar.gz",
                       "https://git.savannah.gnu.org/cgit/gnulib.git/snapshot/gnulib-8e128e.tar.gz"])

        # libtool 2.2.4
        self.get_file("https://mirrors.kernel.org/gnu/libtool/libtool-2.2.4.tar.bz2")

        # automake 1.10.3
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.10.3.tar.bz2")

        # autoconf 2.65
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.65.tar.bz2")

        # gcc 4.0.4
        self.get_file("https://mirrors.kernel.org/gnu/gcc/gcc-4.0.4/gcc-core-4.0.4.tar.bz2",
                      output="gcc-4.0.4.tar.bz2")

        # musl 1.2.2
        self.get_file("https://musl.libc.org/releases/musl-1.2.2.tar.gz")

        # bash 5.1
        self.get_file("https://mirrors.kernel.org/gnu/bash/bash-5.1.tar.gz")

        # xz 5.0.5
        self.get_file("https://tukaani.org/xz/xz-5.0.5.tar.bz2")

        # automake 1.11.2
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.11.2.tar.bz2")

        # autoconf 2.69
        self.get_file("https://mirrors.kernel.org/gnu/autoconf/autoconf-2.69.tar.xz")

        # automake 1.15.1
        self.get_file("https://mirrors.kernel.org/gnu/automake/automake-1.15.1.tar.xz")

        # tar 1.34
        self.get_file(["https://mirrors.kernel.org/gnu/tar/tar-1.34.tar.xz",
                       "https://git.savannah.gnu.org/cgit/gnulib.git/snapshot/gnulib-30820c.tar.gz"])

        # gmp 6.2.1
        self.get_file("https://mirrors.kernel.org/gnu/gmp/gmp-6.2.1.tar.xz")

        # autoconf archive 2021.02.19
        self.get_file("https://mirrors.kernel.org/gnu/autoconf-archive/autoconf-archive-2021.02.19.tar.xz")

        # coreutils 8.32
        self.get_file(["https://mirrors.kernel.org/gnu/coreutils/coreutils-8.32.tar.gz",
                       "https://git.savannah.gnu.org/cgit/gnulib.git/snapshot/gnulib-d279bc.tar.gz"])

        # mpfr 4.1.0
        self.get_file("https://mirrors.kernel.org/gnu/mpfr/mpfr-4.1.0.tar.xz")

        # mpc 1.2.1
        self.get_file("https://mirrors.kernel.org/gnu/mpc/mpc-1.2.1.tar.gz")
