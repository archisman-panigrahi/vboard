Name:           vboard
Version:        2.9.0
Release:        1%{?dist}
Summary:        Wayland virtual keyboard with modifier key support

License:        GPL-3.0-only
URL:            https://github.com/archisman-panigrahi/vboard
Source0:        %{url}/archive/refs/tags/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  desktop-file-utils
BuildRequires:  gobject-introspection
BuildRequires:  gtk3
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  python3-devel
BuildRequires:  python3-gobject

Requires:       gobject-introspection
Requires:       gtk3
Requires:       gtk-layer-shell
Requires:       python3-cairo
Requires:       python3-gobject
Requires:       python3-uinput
Recommends:     hunspell-en-US
Recommends:     hunspell-uk
Suggests:       libappindicator-gtk3

%description
Vboard is a lightweight virtual keyboard for Linux desktop systems. It supports
Wayland on KDE Plasma, modifier and navigation keys, configurable layouts,
Hunspell word suggestions, and gesture typing.


%package plasma
Summary:        KDE Plasma integration for Vboard
Requires:       %{name} = %{version}-%{release}
Requires:       plasma-workspace
Requires:       plasma5support
Requires:       plasma-keyboard
Supplements:    (%{name} and plasma-workspace)

%description plasma
This package provides the Plasma 6 panel and desktop widget for showing or
hiding Vboard.


%prep
%autosetup


%build
%meson
%meson_build


%install
%meson_install

rm -f %{buildroot}%{_datadir}/vboard/LICENSE

install -Dpm0644 udev/70-vboard-uinput.rules \
    %{buildroot}%{_prefix}/lib/udev/rules.d/70-vboard-uinput.rules
install -Dpm0644 packaging/rpm/vboard-uinput.conf \
    %{buildroot}%{_prefix}/lib/modules-load.d/vboard-uinput.conf

install -d %{buildroot}%{_datadir}/plasma/plasmoids/io.github.keefeere.vboard-toggle
cp -a plasmoid/package/. \
    %{buildroot}%{_datadir}/plasma/plasmoids/io.github.keefeere.vboard-toggle/


%check
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/io.github.archisman-panigrahi.vboard.desktop
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/io.github.archisman-panigrahi.vboard-plasma-keyboard.desktop
python3 -m unittest discover -s tests -v


%files
%license LICENSE
%doc README.md
%{_bindir}/vboard
%{_datadir}/applications/io.github.archisman-panigrahi.vboard.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.archisman-panigrahi.vboard.svg
%{_datadir}/vboard/
%{_prefix}/lib/modules-load.d/vboard-uinput.conf
%{_prefix}/lib/udev/rules.d/70-vboard-uinput.rules


%files plasma
%{_datadir}/plasma/plasmoids/io.github.keefeere.vboard-toggle/
%{_datadir}/applications/io.github.archisman-panigrahi.vboard-plasma-keyboard.desktop
%{_libexecdir}/vboard-plasma-keyboard


%changelog
* Sat Sep 05 2026 Chechulin Serhii <78239416+keefeere@users.noreply.github.com> - 2.9.0-1
- Add true dock mode, KWin text-field auto-show, and secure Plasma Keyboard integration

* Mon Aug 24 2026 Chechulin Serhii <78239416+keefeere@users.noreply.github.com> - 2.8.0-1
- Add function and navigation keys, secondary layouts, and reliable minimized startup

* Sun Aug 23 2026 Chechulin Serhii <78239416+keefeere@users.noreply.github.com> - 2.7.1-1
- Add Ukrainian layout, Plasma integration, and Fedora packaging
