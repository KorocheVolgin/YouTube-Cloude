"""Freetype recipe with SourceForge mirror.

Upstream p4a recipe downloads from download.savannah.gnu.org which is
frequently 502 Bad Gateway from GitHub Actions runners. This override
uses the SourceForge mirror which is more reliable.
"""

from pythonforandroid.recipe import Recipe
from pythonforandroid.logger import shprint, info
from pythonforandroid.util import current_directory
from os.path import join, exists
from multiprocessing import cpu_count
import sh


class FreetypeRecipe(Recipe):
    version = '2.14.1'
    # Changed from Savannah to SourceForge (more reliable)
    url = 'https://downloads.sourceforge.net/project/freetype/freetype2/{version}/freetype-{version}.tar.gz'
    built_libraries = {'libfreetype.so': 'objs/.libs'}

    def get_recipe_env(self, arch=None, with_harfbuzz=False):
        env = super().get_recipe_env(arch)
        if with_harfbuzz:
            harfbuzz_build = self.get_recipe(
                'harfbuzz', self.ctx
            ).get_build_dir(arch.arch)
            freetype_install = join(self.get_build_dir(arch.arch), 'install')

            env['HARFBUZZ_CFLAGS'] = '-I{harfbuzz} -I{harfbuzz}/src'.format(
                harfbuzz=harfbuzz_build
            )
            env['HARFBUZZ_LIBS'] = (
                '-L{freetype}/lib -lfreetype '
                '-L{harfbuzz}/src/.libs -lharfbuzz'.format(
                    freetype=freetype_install, harfbuzz=harfbuzz_build
                )
            )

        # android's zlib support
        zlib_lib_path = arch.ndk_lib_dir_versioned
        zlib_includes = self.ctx.ndk.sysroot_include_dir

        def add_flag_if_not_added(flag, env_key):
            if flag not in env[env_key]:
                env[env_key] += flag

        add_flag_if_not_added(' -I' + zlib_includes, 'CFLAGS')
        add_flag_if_not_added(' -L' + zlib_lib_path, 'LDFLAGS')
        add_flag_if_not_added(' -lz', 'LDLIBS')

        return env

    def build_arch(self, arch, with_harfbuzz=False):
        env = self.get_recipe_env(arch, with_harfbuzz=with_harfbuzz)

        harfbuzz_in_recipes = 'harfbuzz' in self.ctx.recipe_build_order
        prefix_path = self.get_build_dir(arch.arch)
        if harfbuzz_in_recipes and not with_harfbuzz:
            prefix_path = join(prefix_path, 'install')

        config_args = {
            '--host={}'.format(arch.command_prefix),
            '--prefix={}'.format(prefix_path),
            '--without-bzip2',
            '--without-brotli',
            '--with-png=no',
        }
        if not harfbuzz_in_recipes:
            info('Build freetype (without harfbuzz)')
            config_args = config_args.union(
                {'--disable-static',
                 '--enable-shared',
                 '--with-harfbuzz=no',
                 '--with-zlib=yes',
                 }
            )
        elif not with_harfbuzz:
            info('Build freetype for First time (without harfbuzz)')
            config_args = config_args.union(
                {'--disable-shared', '--with-harfbuzz=no', '--with-zlib=no'}
            )
        else:
            info('Build freetype for Second time (with harfbuzz)')
            config_args = config_args.union(
                {'--disable-static',
                 '--enable-shared',
                 '--with-harfbuzz=yes',
                 '--with-zlib=yes',
                 }
            )
        info('Configure args are:\n\t-{}'.format('\n\t-'.join(config_args)))

        with current_directory(self.get_build_dir(arch.arch)):
            configure = sh.Command('./configure')
            shprint(configure, *config_args, _env=env)
            shprint(sh.make, '-j', str(cpu_count()), _env=env)

            if not with_harfbuzz and harfbuzz_in_recipes:
                info('Installing freetype (first time build without harfbuzz)')
                shprint(sh.make, 'install', _env=env)
                shprint(sh.make, 'distclean', _env=env)

    def install_libraries(self, arch):
        if not exists(list(self.get_libraries(arch))[0]):
            return
        self.install_libs(arch, *self.get_libraries(arch))


recipe = FreetypeRecipe()
