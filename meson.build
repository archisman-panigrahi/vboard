project('vboard', version: '1.0.0')

vboard_data_dir = join_paths(get_option('datadir'), 'vboard')
scripts_install_dir = join_paths(vboard_data_dir, 'scripts')
applications_dir = join_paths(get_option('datadir'), 'applications')

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
  'scripts/install-plasma-osk.sh',
  'scripts/uninstall-plasma-osk.sh',
  'scripts/install-kwin-rule.sh',
  'scripts/uninstall-kwin-rule.sh',
  install_dir: scripts_install_dir,
  install_mode: 'rwxr-xr-x',
)

desktop_conf = configuration_data()
desktop_conf.set('VBOARD_EXEC', 'vboard')
configured_desktop = configure_file(
  input: 'meson/org.mdev.vboard.desktop.in',
  output: 'org.mdev.vboard.desktop',
  configuration: desktop_conf,
)

install_data(configured_desktop, install_dir: applications_dir)
install_data(configured_desktop, install_dir: vboard_data_dir)

meson.add_install_script(
  'scripts/meson-post-install.sh',
  join_paths(get_option('prefix'), scripts_install_dir),
  get_option('prefix'),
)
