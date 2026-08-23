/*
    SPDX-FileCopyrightText: 2026 Chechulin Serhii
    SPDX-License-Identifier: GPL-3.0-or-later
*/

import QtQuick
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    readonly property string iconName: "input-keyboard"
    readonly property string toggleCommand: "/usr/bin/env vboard --toggle"
    property bool busy: false

    Plasmoid.icon: iconName
    Plasmoid.title: i18n("Vboard Keyboard")
    toolTipMainText: Plasmoid.title
    toolTipSubText: i18n("Show or hide the on-screen keyboard")
    preferredRepresentation: Plasmoid.formFactor === PlasmaCore.Types.Planar
        ? fullRepresentation
        : compactRepresentation

    function toggleKeyboard() {
        if (busy) {
            return;
        }

        busy = true;
        executable.connectSource(toggleCommand);
    }

    Plasma5Support.DataSource {
        id: executable

        engine: "executable"

        onNewData: function(sourceName, data) {
            disconnectSource(sourceName);
            root.busy = false;
        }

        onSourceDisconnected: function(sourceName) {
            root.busy = false;
        }
    }

    compactRepresentation: Item {
        implicitWidth: Kirigami.Units.iconSizes.medium
        implicitHeight: Kirigami.Units.iconSizes.medium
        Layout.minimumWidth: Kirigami.Units.iconSizes.medium
        Layout.minimumHeight: Kirigami.Units.iconSizes.medium
        Layout.preferredWidth: Kirigami.Units.iconSizes.medium
        Layout.preferredHeight: Kirigami.Units.iconSizes.medium

        Kirigami.Icon {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height) * 1.3
            height: width
            source: root.iconName
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            hoverEnabled: true
            onClicked: root.toggleKeyboard()
        }
    }

    fullRepresentation: MouseArea {
        id: button

        Layout.minimumWidth: Kirigami.Units.iconSizes.medium
        Layout.minimumHeight: Kirigami.Units.iconSizes.medium
        Layout.preferredWidth: Kirigami.Units.iconSizes.large
        Layout.preferredHeight: Kirigami.Units.iconSizes.large
        activeFocusOnTab: true
        cursorShape: Qt.PointingHandCursor
        hoverEnabled: true

        Accessible.name: root.toolTipSubText
        Accessible.role: Accessible.Button

        onClicked: root.toggleKeyboard()
        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
                root.toggleKeyboard();
                event.accepted = true;
            }
        }

        Kirigami.Icon {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            active: button.containsMouse || button.activeFocus
            opacity: root.busy ? 0.6 : 1.0
            source: root.iconName

            Behavior on opacity {
                NumberAnimation {
                    duration: Kirigami.Units.shortDuration
                }
            }
        }
    }
}
