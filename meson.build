project('vboard', version: '1.3')

vboard_data_dir = join_paths(get_option('datadir'), 'vboard')
vboard_python_dir = join_paths(vboard_data_dir, 'vboard')
scripts_install_dir = join_paths(vboard_data_dir, 'scripts')
udev_data_dir = join_paths(vboard_data_dir, 'udev')
applications_dir = join_paths(get_option('datadir'), 'applications')
icons_dir = join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps')

install_data(
  'vboard.py',
  install_dir: get_option('bindir'),
  rename: 'vboard',
  install_mode: 'rwxr-xr-x',
)

install_data(
  'uinput.md',
  'LICENSE',
  install_dir: vboard_data_dir,
)

install_data(
  'udev/70-vboard-uinput.rules',
  install_dir: udev_data_dir,
)

install_data(
  files(
    'vboard/__init__.py',
    'vboard/__main__.py',
    'vboard/app.py',
    'vboard/constants.py',
    'vboard/environment.py',
    'vboard/gtk.py',
    'vboard/input_backends.py',
    'vboard/suggestions.py',
    'vboard/window.py',
  ),
  install_dir: vboard_python_dir,
)

install_data(
  'io.github.archisman-panigrahi.vboard.svg',
  install_dir: icons_dir,
)

install_data(
  'scripts/install-kwin-rule.sh',
  'scripts/uninstall-kwin-rule.sh',
  'scripts/meson-post-install.sh',
  'scripts/setup-uinput.sh',
  install_dir: scripts_install_dir,
  install_mode: 'rwxr-xr-x',
)

desktop_conf = configuration_data()
desktop_conf.set('VBOARD_EXEC', 'vboard')
configured_desktop = configure_file(
  input: 'meson/io.github.archisman-panigrahi.vboard.desktop.in',
  output: 'io.github.archisman-panigrahi.vboard.desktop',
  configuration: desktop_conf,
)

install_data(configured_desktop, install_dir: applications_dir)

meson.add_install_script(
  'scripts/meson-post-install.sh',
  join_paths(get_option('prefix'), scripts_install_dir),
  get_option('prefix'),
  join_paths(get_option('prefix'), applications_dir),
)

run_target(
  'uninstall-local',
  command: [
    'bash',
    files('scripts/meson-uninstall.sh'),
    get_option('prefix'),
    get_option('bindir'),
    get_option('datadir'),
  ],
)
