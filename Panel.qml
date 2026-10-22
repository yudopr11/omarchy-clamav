pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.yudopr11.omarchy-clamav-control"
  ipcTarget: "io.github.yudopr11.omarchy-clamav-control"

  readonly property string directory: decodeURIComponent(Qt.resolvedUrl(".").toString().replace(/^file:\/\//, ""))
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property int refreshIntervalSec: Math.max(10, Math.min(600, Number(setting("refreshIntervalSec", 60)) || 60))
  readonly property real staleAfter: (opened ? 5 : refreshIntervalSec) * 1000 + 15000
  readonly property real markSize: Math.max(12, Math.round(Style.bar.iconSlot * 0.56))
  readonly property real openPanelIndicatorWidth: markSize
  property var state: ({ services: {}, configs: {}, errors: [] })
  property var monitor: ({recent: [], total: 0, activeCount: 0, lastUpdateEpoch: 0, logReadable: false})
  property real lastGood: 0
  property real lastMonitor: 0
  property real now: Date.now()
  property bool statusFailed: true
  property bool monitorFailed: true
  property string packageState: "unknown"
  property bool scannerDirty: false
  property bool updaterDirty: false
  property string applying: ""
  property string message: ""
  property string statusError: ""
  property string confirmation: ""
  property bool confirmationCancel: true
  property bool policyDetailsVisible: false
  property var pendingAction: []
  readonly property bool stale: statusFailed || now - lastGood > staleAfter
  readonly property bool historyStale: monitorFailed || now - lastMonitor > staleAfter
  readonly property bool protectionKnown: !stale && servicesKnown(["scanner", "daemon", "socket"])
  readonly property bool protectionActive: protectionKnown && serviceState("scanner").active === "active" && serviceState("daemon").active === "active"
  readonly property bool busy: actionProc.running
  property int cursor: 0
  property string tab: "overview"
  readonly property var tabs: ["overview", "services", "settings"]
  readonly property var pageItems: ({
    "overview": [refreshButton, installButton, helperInstallButton, logButton],
    "services": [policyDetailsButton, prepareQuarantine, daemonStart, daemonStop, daemonBoot, daemonDisableBoot, scannerStart, scannerStop, scannerBoot, updaterStart, updaterStop, updaterBoot],
    "settings": [reloadButton, includeField, excludeField, sizeField, saveScanner, checksField, saveUpdater]
  })
  readonly property var cursorItems: pageItems[tab].filter(function(item) { return item.visible && item.enabled })
  onCursorItemsChanged: cursor = Math.min(cursor, Math.max(0, cursorItems.length - 1))

  function setTab(page) {
    if (tabs.indexOf(page) < 0) return
    confirmation = ""
    pendingAction = []
    tab = page
    cursor = 0
    scroll.contentY = 0
    Qt.callLater(function() { keys.forceActiveFocus() })
  }


  function serviceState(kind) {
    return state.services[kind] || { active: "unknown", boot: "unknown", policy: "" }
  }
  function servicesKnown(kinds) {
    for (var i = 0; i < kinds.length; i++) {
      if (["active", "inactive", "failed"].indexOf(serviceState(kinds[i]).active) < 0) return false
    }
    return true
  }
  function canService(kind, action) {
    var kinds = kind === "daemon" ? (action === "stop" || action === "disable" ? ["scanner", "socket", "daemon"] : ["socket", "daemon"]) : (kind === "scanner" && (action === "start" || action === "enable") ? ["socket", "daemon", "scanner"] : [kind])
    if (action === "stop" || action === "disable") {
      for (var i = 0; i < kinds.length; i++) if (servicesKnown([kinds[i]])) return true
      return false
    }
    return servicesKnown(kinds)
  }
  function bootAction(kind) {
    return serviceState(kind).boot === "enabled" ? "disable" : "enable"
  }
  function bootKnown(kind) {
    return ["enabled", "disabled"].indexOf(serviceState(kind).boot) >= 0
  }
  function refresh() {
    if (!packageProc.running) packageProc.running = true
    if (!statusProc.running) statusProc.running = true
    if (!monitorProc.running) monitorProc.running = true
  }
  function loadFields() {
    var scanner = state.configs.scanner
    var updater = state.configs.updater
    if (scanner && !scannerDirty) {
      includeField.text = JSON.stringify(scanner.values.include)
      excludeField.text = JSON.stringify(scanner.values.exclude)
      sizeField.text = scanner.values.maxSize
      includeField.revision = scanner.revision
    }
    if (updater && !updaterDirty) {
      checksField.text = String(updater.values.checks)
      checksField.revision = updater.revision
    }
  }
  function request(args) {
    if (busy || stale || (args[0] === "service" && !canService(args[1], args[2]))) return
    applying = args[0] === "apply" ? args[1] : ""
    message = ""
    actionProc.command = ["/usr/bin/timeout", "150", "pkexec", "/usr/local/bin/omarchy-clamav-control"].concat(args)
    actionProc.running = true
  }
  function serviceAction(kind, action) {
    var args = ["service", kind, action]
    if ((kind === "scanner" || kind === "daemon") && (action === "start" || action === "enable")) {
      pendingAction = args
      confirmationCancel = true
      confirmation = "Starting/enabling protection uses the existing system policy. It can move or remove files. This plugin does not change that policy. Continue?"
      Qt.callLater(function() { scroll.contentY = servicesPage.mapToItem(content, 0, 0).y; keys.forceActiveFocus() })
    } else request(args)
  }
  function save(kind) {
    try {
      var data = kind === "scanner" ? {include: JSON.parse(includeField.text), exclude: JSON.parse(excludeField.text), maxSize: sizeField.text} : {checks: Number(checksField.text)}
      request(["apply", kind, kind === "scanner" ? includeField.revision : checksField.revision, JSON.stringify(data)])
    } catch (e) { message = "Include/exclude fields must be JSON arrays of absolute directory paths." }
  }
  function moveCursor(delta) {
    if (!cursorItems.length) return
    for (var i = 0; i < cursorItems.length; i++) {
      cursor = (cursor + delta + cursorItems.length) % cursorItems.length
      if (cursorItems[cursor].enabled && cursorItems[cursor].visible) break
    }
    var item = cursorItems[cursor]
    if (item === includeField || item === excludeField || item === sizeField || item === checksField) item.forceActiveFocus()
    else keys.forceActiveFocus()
    var y = item.mapToItem(content, 0, 0).y
    if (y < scroll.contentY) scroll.contentY = y
    else if (y + item.height > scroll.contentY + scroll.height) scroll.contentY = y + item.height - scroll.height
  }
  onOpenedChanged: {
    confirmation = ""
    if (opened) { refresh(); Qt.callLater(function() { keys.forceActiveFocus() }) }
  }

  Process {
    id: packageProc
    command: ["/usr/bin/timeout", "10", "omarchy-pkg-present", "clamav"]
    onExited: function(code) { root.packageState = code === 0 ? "installed" : (code === 1 ? "absent" : "unknown") }
  }
  Process {
    id: packageInstallProc
    command: ["omarchy-launch-terminal", "bash", root.directory + "/bin/install-clamav.sh"]
    stderr: StdioCollector { id: packageInstallError; waitForEnd: true }
    onExited: function(code) {
      if (code !== 0) root.message = packageInstallError.text.trim() || "Could not launch the installer terminal."
      root.refresh()
    }
  }
  Process {
    id: helperInstallProc
    command: ["omarchy-launch-terminal", "bash", root.directory + "/bin/install-helper.sh"]
    stderr: StdioCollector { id: helperInstallError; waitForEnd: true }
    onExited: function(code) {
      if (code !== 0) root.message = helperInstallError.text.trim() || "Could not launch or complete the helper installer terminal."
      root.refresh()
    }
  }
  Timer {
    interval: 5000
    running: true
    repeat: true
    onTriggered: if (!packageProc.running) packageProc.running = true
  }
  Process {
    id: statusProc
    command: ["/usr/bin/timeout", "15", "/usr/local/bin/omarchy-clamav-control", "status"]
    stdout: StdioCollector { id: statusOutput; waitForEnd: true }
    stderr: StdioCollector { id: statusStderr; waitForEnd: true }
    onExited: function(code) {
      root.statusFailed = true
      try {
        if (code !== 0 || statusOutput.text.length > 131072) throw new Error(statusStderr.text || "Control helper unavailable or timed out. Install it explicitly; see README.")
        var data = JSON.parse(statusOutput.text)
        if (!data.services || !data.configs || !Array.isArray(data.errors)) throw new Error("Invalid helper status")
        root.state = data
        root.lastGood = Date.now()
        root.statusFailed = false
        root.statusError = ""
        root.loadFields()
      } catch (e) { root.statusError = String(e) }
    }
  }
  Process {
    id: monitorProc
    command: ["/usr/bin/timeout", "15", "bash", root.directory + "/bin/status.sh"]
    stdout: StdioCollector { id: monitorOutput; waitForEnd: true }
    onExited: function(code) {
      root.monitorFailed = true
      try {
        if (code !== 0 || monitorOutput.text.length > 65536) return
        var data = JSON.parse(monitorOutput.text)
        if (!Array.isArray(data.recent)) return
        root.monitor = data
        root.lastMonitor = Date.now()
        root.monitorFailed = false
      } catch (e) {}
    }
  }
  Process {
    id: actionProc
    stdout: StdioCollector { id: actionOutput; waitForEnd: true }
    stderr: StdioCollector { id: actionStderr; waitForEnd: true }
    onExited: function(code) {
      if (code === 0) {
        try { root.message = JSON.parse(actionOutput.text).message } catch (e) { root.message = "Operation completed; refresh to verify." }
        if (root.applying === "scanner") root.scannerDirty = false
        if (root.applying === "updater") root.updaterDirty = false
      } else root.message = actionStderr.text.trim() || "Authentication cancelled, timed out, or operation failed. Some service changes may have completed; check actual state."
      root.refresh()
    }
  }
  Timer {
    interval: root.opened ? 5000 : root.refreshIntervalSec * 1000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }
  Timer {
    interval: 1000
    repeat: true
    running: true
    onTriggered: root.now = Date.now()
  }

  implicitWidth: markSize + Style.space(12)
  implicitHeight: button.implicitHeight
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    active: false
    useActiveColor: false
    foreground: !root.historyStale && root.monitor.activeCount > 0 ? Color.urgent : (root.bar ? root.bar.barForeground : Color.foreground)
    opacity: root.protectionActive ? 1.0 : 0.45
    tooltipText: !root.protectionKnown ? "ClamAV: status unknown/stale" : (root.protectionActive ? "ClamAV: on-access active" : "ClamAV: on-access inactive")
    onPressed: function(mouseButton) { if (mouseButton === Qt.RightButton) root.refresh(); else root.toggle() }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keys
    contentWidth: popup.fittedContentWidth(Style.space(520))
    contentHeight: popup.fittedContentHeight(Math.min(content.implicitHeight, Style.space(600)))
    PanelKeyCatcher {
      id: keys
      anchors.fill: parent
      blocked: includeField.activeFocus || excludeField.activeFocus || sizeField.activeFocus || checksField.activeFocus
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onMoveRequested: function(dx, dy) { if (root.confirmation) root.confirmationCancel = !root.confirmationCancel; else if (dx) root.setTab(root.tabs[(root.tabs.indexOf(root.tab) + dx + root.tabs.length) % root.tabs.length]); else root.moveCursor(dy) }
      onActivateRequested: {
        if (root.confirmation) { root.confirmation = ""; if (!root.confirmationCancel) root.request(root.pendingAction) }
        else if (root.cursorItems.length && root.cursorItems[root.cursor].visible && root.cursorItems[root.cursor].enabled && root.cursorItems[root.cursor].clicked) root.cursorItems[root.cursor].clicked()
      }
      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        Column {
          id: content
          width: parent.width
          spacing: Style.space(8)
          component Label: Text {
            width: parent.width
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
          component Card: Item {
            id: card
            default property alias contents: cardBody.data
            width: parent.width
            implicitHeight: cardBody.implicitHeight + Style.space(24)
            Rectangle {
              anchors.fill: parent
              radius: Style.space(10)
              color: Util.alpha(root.foreground, 0.035)
              border.color: Util.alpha(root.foreground, 0.12)
            }
            Column {
              id: cardBody
              x: Style.space(12)
              y: Style.space(12)
              width: card.width - Style.space(24)
              spacing: Style.space(10)
            }
          }
          component Heading: Label {
            font.bold: true
            font.pixelSize: Style.font.body
          }
          component StatusPill: Rectangle {
            id: pill
            property string text: ""
            property bool failed: false
            property bool active: false
            width: Math.min(implicitWidth, parent.width)
            implicitWidth: pillText.implicitWidth + Style.space(20)
            implicitHeight: pillText.implicitHeight + Style.space(8)
            radius: height / 2
            color: Util.alpha(failed ? Color.urgent : root.foreground, active ? 0.12 : 0.06)
            border.color: Util.alpha(failed ? Color.urgent : root.foreground, 0.2)
            Text {
              id: pillText
              anchors.centerIn: parent
              width: parent.width - Style.space(20)
              text: pill.text
              textFormat: Text.PlainText
              elide: Text.ElideRight
              color: pill.failed ? Color.urgent : root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: pill.active
            }
          }
          component ServiceStatus: Flow {
            id: serviceStatus
            required property string kind
            readonly property string runtime: root.stale ? "unknown" : root.serviceState(kind).active
            width: parent.width
            spacing: Style.space(8)
            StatusPill { text: "Runtime: " + serviceStatus.runtime; active: serviceStatus.runtime === "active"; failed: serviceStatus.runtime === "failed" }
            StatusPill { text: "Boot: " + (root.stale ? "unknown" : root.serviceState(serviceStatus.kind).boot) }
          }
          component Actions: Flow {
            width: parent.width
            spacing: Style.space(6)
          }
          component Action: Button {
            property string serviceKind: ""
            property string operation: ""
            hasCursor: root.cursorItems[root.cursor] === this
            width: Math.min(implicitWidth, parent.width)
            foreground: root.foreground
            fontFamily: root.fontFamily
            focusable: true
            enabled: !root.busy && !root.stale && (serviceKind === "" || root.canService(serviceKind, operation)) && !root.confirmation
          }
          Label { text: "ClamAV Control"; font.pixelSize: Style.font.title; font.bold: true }
          Actions {
            StatusPill {
              text: !root.protectionKnown ? "Status unknown / stale" : (root.protectionActive ? "On-access active" : (root.serviceState("scanner").active === "failed" || root.serviceState("daemon").active === "failed" || root.serviceState("socket").active === "failed" ? "Protection failed" : "On-access inactive"))
              active: root.protectionActive
              failed: root.protectionKnown && (root.serviceState("scanner").active === "failed" || root.serviceState("daemon").active === "failed" || root.serviceState("socket").active === "failed")
            }
            StatusPill { text: "ClamAV · " + root.packageState }
          }
          Label { text: "Runtime and boot settings are independent. Monitoring is not a coverage verdict." }
          Label { visible: !!root.statusError; text: root.statusError; color: Color.urgent }
          Label { visible: root.state.errors.length > 0; text: root.state.errors.join("\n"); color: Color.urgent }
          Label { visible: !!root.message; text: root.message }
          Row {
            width: parent.width
            height: Style.space(32)
            Repeater {
              model: ["Overview", "Services", "Settings"]
              delegate: Item {
                id: tabItem
                required property string modelData
                required property int index
                readonly property bool current: root.tab === root.tabs[index]
                width: parent.width / 3
                height: parent.height
                CursorSurface {
                  anchors.fill: parent
                  anchors.bottomMargin: Style.space(2)
                  hasCursor: tabMouse.containsMouse
                  current: tabItem.current
                  foreground: root.foreground
                }
                Text {
                  anchors.centerIn: parent
                  text: tabItem.modelData
                  color: tabItem.current ? root.foreground : Qt.darker(root.foreground, 1.5)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: tabItem.current
                }
                Rectangle {
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.bottom: parent.bottom
                  anchors.margins: Style.spacing.md
                  anchors.bottomMargin: 0
                  height: Style.space(2)
                  radius: height / 2
                  color: Color.accent
                  opacity: tabItem.current ? 1 : 0
                }
                MouseArea {
                  id: tabMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.setTab(root.tabs[tabItem.index])
                }
              }
            }
          }
          Column {
            id: overviewPage
            width: parent.width
            spacing: Style.space(12)
            visible: root.tab === "overview"
            Button { id: refreshButton; hasCursor: root.cursorItems[root.cursor] === refreshButton; width: parent.width; text: "Refresh status"; focusable: true; onClicked: root.refresh() }
            Card {
              id: setupCard
              Heading { text: "Setup" }
              Label { text: "Install ClamAV with the Omarchy installer, then install / update the control helper. Both open a visible terminal." }
              Label { text: "1. Install ClamAV, then 2. Install / update control helper.\n3. Settings: choose watched paths and Apply scanner / updater setup.\n4. Services: start updater, wait for databases, then daemon / scanner. Boot is optional; nothing starts automatically." }
              Label { text: "ClamAV package: " + root.packageState }
              Button { id: installButton; visible: root.packageState === "absent"; width: parent.width; text: "Install ClamAV"; focusable: true; hasCursor: root.cursorItems[root.cursor] === installButton; enabled: !packageInstallProc.running; onClicked: packageInstallProc.running = true }
              Button { id: helperInstallButton; width: parent.width; text: "Install / update helper"; focusable: true; hasCursor: root.cursorItems[root.cursor] === helperInstallButton; enabled: !helperInstallProc.running; onClicked: helperInstallProc.running = true }
            }
            Card {
              id: historyCard
              Heading { text: "Recent history" }
              Label { text: root.historyStale ? "History unknown/stale; showing last available records." : (root.monitor.logReadable ? "Last ten logged detections, not a full-system scan. File presence is not a quarantine verdict." : "Detection log unreadable or absent; see README for optional collector setup.") }
              Label { text: "Daily database file modified: " + (root.monitor.lastUpdateEpoch ? new Date(root.monitor.lastUpdateEpoch * 1000).toLocaleString(Qt.locale(), Locale.ShortFormat) : "unknown") + " (not proof of a successful update)" }
              Label { text: root.monitor.total + " logged detections; " + root.monitor.activeCount + " of the last ten paths currently visible to this user. Missing paths may be inaccessible, moved or removed." }
              Repeater {
                model: root.monitor.recent
                Column {
                  id: historyRecord
                  required property var modelData
                  width: parent.width
                  spacing: Style.space(4)
                  Rectangle { width: parent.width; height: Style.space(1); color: Util.alpha(root.foreground, 0.12) }
                  Heading { text: historyRecord.modelData.signature; color: !root.historyStale && historyRecord.modelData.present ? Color.urgent : root.foreground }
                  Label { text: historyRecord.modelData.path }
                  Label { text: new Date(historyRecord.modelData.whenEpoch * 1000).toLocaleString(Qt.locale(), Locale.ShortFormat) + " · " + (historyRecord.modelData.present ? "Path still present" : "Path absent or inaccessible") }
                }
              }
              Button { id: logButton; hasCursor: root.cursorItems[root.cursor] === logButton; width: parent.width; text: "Open detection log"; focusable: true; onClicked: { if (root.bar) root.bar.run("omarchy-launch-editor " + Util.shellQuote(Quickshell.env("HOME") + "/.local/state/omarchy/clamav-detections.log")) } }
            }
          } // End overview
          Column {
            id: servicesPage
            width: parent.width
            spacing: Style.space(8)
            visible: root.tab === "services"
            Label { visible: !!root.confirmation; text: root.confirmation; font.bold: true }
            Button { visible: !!root.confirmation; width: parent.width; text: "Confirm existing policy"; focusable: true; hasCursor: !root.confirmationCancel; onClicked: { root.confirmation = ""; root.request(root.pendingAction) } }
            Button { id: cancelButton; visible: !!root.confirmation; width: parent.width; text: "Cancel"; focusable: true; hasCursor: root.confirmationCancel; onClicked: root.confirmation = "" }
            Card {
              id: policyCard
              Heading { text: "Policy & quarantine" }
              Label { text: "Prepare /root/quarantine requires authentication." }
              Label { text: "Existing service policy may move or remove detected files. This plugin preserves that policy; if details are unknown, inspect the service before starting."; color: root.foreground }
              Button { id: policyDetailsButton; width: parent.width; text: root.policyDetailsVisible ? "Hide policy details" : "Show policy details"; focusable: true; hasCursor: root.cursorItems[root.cursor] === policyDetailsButton; onClicked: root.policyDetailsVisible = !root.policyDetailsVisible }
              Label { visible: root.policyDetailsVisible; text: "ExecStart: " + (root.stale ? "Unknown/stale; inspect systemctl cat clamav-clamonacc.service before starting." : (root.serviceState("scanner").policy || "Unknown; inspect systemctl cat clamav-clamonacc.service before starting.")); color: root.foreground }
              Label { text: root.stale ? "Quarantine readiness unknown/stale" : (root.state.quarantine ? root.state.quarantine.message : "Update helper for quarantine preparation status.") }
              Label { text: "Readiness may be unavailable without authentication (/root is private). Prepare rechecks policy and creates only missing root:root 0700 /root/quarantine; existing permissions and policy stay unchanged. Does not start services." }
              Action { id: prepareQuarantine; text: "Prepare quarantine"; visible: !root.state.quarantine || root.state.quarantine.state !== "ready"; onClicked: root.request(["prepare-quarantine"]) }
            }
            Card {
              id: daemonCard
              Heading { text: "Daemon & socket" }
              ServiceStatus { kind: "daemon" }
              Label { text: "Socket · " + (root.stale ? "unknown" : root.serviceState("socket").active + " · boot " + root.serviceState("socket").boot) }
              Label { text: root.stale ? "Diagnostics unavailable/stale" : (root.serviceState("daemon").diagnostic || "Diagnostics unknown") }
              Heading { text: "Runtime" }
              Label { text: "Start includes socket; stop also stops scanner and socket." }
              Actions {
                Action { id: daemonStart; serviceKind: "daemon"; operation: "start"; text: "Start daemon"; onClicked: root.serviceAction("daemon", "start") }
                Action { id: daemonStop; serviceKind: "daemon"; operation: "stop"; text: "Stop daemon"; onClicked: root.serviceAction("daemon", "stop") }
              }
              Heading { text: "At boot" }
              Label { text: "Enable includes socket; disable also disables scanner and socket. Running services are unchanged." }
              Actions {
                Action { id: daemonBoot; serviceKind: "daemon"; operation: "enable"; text: "Enable at boot"; onClicked: root.serviceAction("daemon", "enable") }
                Action { id: daemonDisableBoot; serviceKind: "daemon"; operation: "disable"; text: "Disable at boot"; onClicked: root.serviceAction("daemon", "disable") }
              }
            }
            Card {
              id: scannerCard
              Heading { text: "On-access scanner" }
              ServiceStatus { kind: "scanner" }
              Label { text: root.stale ? "Diagnostics unavailable/stale" : (root.serviceState("scanner").diagnostic || "Update helper for diagnostics") }
              Heading { text: "Runtime" }
              Label { text: "Start includes daemon/socket dependencies; stop leaves daemon/socket running." }
              Actions {
                Action { id: scannerStart; serviceKind: "scanner"; operation: "start"; text: "Start scanner"; onClicked: root.serviceAction("scanner", "start") }
                Action { id: scannerStop; serviceKind: "scanner"; operation: "stop"; text: "Stop scanner"; onClicked: root.serviceAction("scanner", "stop") }
              }
              Heading { text: "At boot" }
              Actions {
                Action { id: scannerBoot; serviceKind: "scanner"; operation: root.bootAction("scanner"); text: root.bootAction("scanner") + " scanner at boot"; enabled: !root.stale && !root.busy && !root.confirmation && root.bootKnown("scanner"); onClicked: root.serviceAction("scanner", root.bootAction("scanner")) }
              }
            }
            Card {
              id: updaterCard
              Heading { text: "Signature updater" }
              ServiceStatus { kind: "updater" }
              Label { text: root.stale ? "Diagnostics unavailable/stale" : (root.serviceState("updater").diagnostic || "Diagnostics unknown") }
              Heading { text: "Runtime" }
              Actions {
                Action { id: updaterStart; serviceKind: "updater"; operation: "start"; text: "Start updater"; onClicked: root.serviceAction("updater", "start") }
                Action { id: updaterStop; serviceKind: "updater"; operation: "stop"; text: "Stop updater"; onClicked: root.serviceAction("updater", "stop") }
              }
              Heading { text: "At boot" }
              Actions {
                Action { id: updaterBoot; serviceKind: "updater"; operation: root.bootAction("updater"); text: root.bootAction("updater") + " updater at boot"; enabled: !root.stale && !root.busy && !root.confirmation && root.bootKnown("updater"); onClicked: root.serviceAction("updater", root.bootAction("updater")) }
              }
            }
          } // End services
          Column {
            id: settingsPage
            width: parent.width
            spacing: Style.space(8)
            visible: root.tab === "settings"
            Label { text: "Reload discards unsaved edits." }
            Button { id: reloadButton; hasCursor: root.cursorItems[root.cursor] === reloadButton; width: parent.width; text: "Reload fields"; focusable: true; enabled: !root.busy; onClicked: { root.scannerDirty = false; root.updaterDirty = false; root.loadFields() } }
            Card {
              id: scannerSettingsCard
              Heading { text: "Scanner settings" }
              Label { text: "Apply requires authentication and saves configuration only." }
              Label { text: "Include/exclude: JSON arrays of existing absolute directories, e.g. [\"/home\"]. Apply saves only; stop scanner+daemon, then start daemon and scanner to use new settings. Backups remain next to the config." }
              Label { text: "Apply adds a validated daemon exclusion only when absent; existing UID/Uname/root exclusions and quarantine policy stay unchanged. Root-only exclusions do not cover a non-root daemon. Missing User uses the validated clamav default; package Example is removed after validation. No services start." }
              Label { text: root.state.configs.scanner && root.state.configs.scanner.setup ? root.state.configs.scanner.setup.join("\n") : "Install / update control helper on Overview to load setup prerequisites." }
              Label { text: "Include paths" }
              TextField { id: includeField; property string revision: ""; width: parent.width; enabled: !!root.state.configs.scanner && !root.busy; onTextEdited: root.scannerDirty = true; Keys.onEscapePressed: keys.forceActiveFocus() }
              Label { text: "Exclude paths" }
              TextField { id: excludeField; width: parent.width; enabled: includeField.enabled; onTextEdited: root.scannerDirty = true; Keys.onEscapePressed: keys.forceActiveFocus() }
              Label { text: "Maximum on-access size (bytes or K/M/G; 1 byte–4G)" }
              TextField { id: sizeField; width: parent.width; enabled: includeField.enabled; onTextEdited: root.scannerDirty = true; Keys.onEscapePressed: keys.forceActiveFocus() }
              Action { id: saveScanner; text: "Apply scanner settings"; enabled: includeField.enabled && !root.stale && !root.confirmation; onClicked: root.save("scanner") }
            }
            Card {
              id: updaterSettingsCard
              Heading { text: "Signature updates" }
              Label { text: "Apply requires authentication and saves configuration only." }
              Label { text: root.state.configs.updater && root.state.configs.updater.setup ? root.state.configs.updater.setup.join("\n") : "" }
              Heading { text: "Checks per day (1–50)" }
              Label { text: "Apply completes package Example setup. Restart updater afterward; wait for initial databases before starting scanner." }
              TextField { id: checksField; property string revision: ""; width: parent.width; enabled: !!root.state.configs.updater && !root.busy; onTextEdited: root.updaterDirty = true; Keys.onEscapePressed: keys.forceActiveFocus() }
              Action { id: saveUpdater; text: "Apply update frequency"; enabled: checksField.enabled && !root.stale && !root.confirmation; onClicked: root.save("updater") }
            }
          } // End settings
        }
      }
    }
  }
}
