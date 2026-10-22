"""Static QML wiring checks; these do not replace live focus/rendering checks."""
from pathlib import Path
import unittest


PANEL = Path(__file__).resolve().parents[1] / "Panel.qml"


class PanelTabsTests(unittest.TestCase):
    def test_pages_and_cursor_scope(self):
        source = PANEL.read_text()
        for page, controls in {
            "overview": ["refreshButton", "installButton", "helperInstallButton", "logButton"],
            "services": ["policyDetailsButton", "prepareQuarantine", "daemonStart", "daemonStop", "daemonBoot", "daemonDisableBoot", "scannerStart", "scannerStop", "scannerBoot", "updaterStart", "updaterStop", "updaterBoot"],
            "settings": ["reloadButton", "includeField", "excludeField", "sizeField", "saveScanner", "checksField", "saveUpdater"],
        }.items():
            start = source.index('id: ' + page + 'Page')
            end = source.index('// End ' + page, start)
            body = source[start:end]
            self.assertIn('visible: root.tab === "' + page + '"', body)
            for control in controls:
                self.assertIn('id: ' + control + ';', body)
            self.assertIn('"' + page + '": [' + ', '.join(controls) + ']', source)
        self.assertIn('pageItems[tab].filter(function(item) { return item.visible && item.enabled })', source)

    def test_policy_details_are_optional_and_neutral(self):
        source = PANEL.read_text()
        self.assertIn('property bool policyDetailsVisible: false', source)
        services = source[source.index('id: servicesPage'):source.index('// End services')]
        self.assertNotIn('Local exploration', services)
        button = next(line for line in services.splitlines() if 'id: policyDetailsButton;' in line)
        self.assertIn('root.policyDetailsVisible ? "Hide policy details" : "Show policy details"', button)
        self.assertIn('onClicked: root.policyDetailsVisible = !root.policyDetailsVisible', button)
        self.assertIn('hasCursor: root.cursorItems[root.cursor] === policyDetailsButton', button)
        details = next(line for line in services.splitlines() if 'root.serviceState("scanner").policy' in line)
        self.assertIn('visible: root.policyDetailsVisible', details)
        self.assertIn('root.stale ?', details)
        self.assertIn('color: root.foreground', details)
        summary = next(line for line in services.splitlines() if 'Existing service policy may move or remove detected files.' in line)
        self.assertIn('color: root.foreground', summary)
        self.assertIn('unknown', summary.lower())

    def test_setup_guidance_and_failure_diagnostics(self):
        source = PANEL.read_text()
        self.assertIn('1. Install ClamAV', source)
        self.assertIn('2. Install / update control helper', source)
        self.assertIn('3. Settings', source)
        self.assertIn('4. Services', source)
        self.assertIn('root.state.configs.scanner.setup', source)
        self.assertIn('root.serviceState("scanner").diagnostic', source)
        self.assertIn('daemon exclusion only when absent', source)
        self.assertIn('root.state.configs.updater.setup', source)

    def test_quarantine_explicit_authenticated_wiring(self):
        source = PANEL.read_text()
        self.assertIn('root.request(["prepare-quarantine"])', source)
        self.assertIn('root.state.quarantine.message', source)
        self.assertIn('id: prepareQuarantine;', source)
        self.assertIn('Does not start services', source)
        self.assertIn('Readiness may be unavailable without authentication', source)

    def test_navigation_and_confirmation(self):
        source = PANEL.read_text()
        start = source.index('function setTab(')
        body = source[start:source.index('function serviceState', start)]
        for statement in ['confirmation = ""', 'pendingAction = []', 'cursor = 0', 'scroll.contentY = 0', 'keys.forceActiveFocus()']:
            self.assertIn(statement, body)
        self.assertIn('else if (dx) root.setTab', source)
        self.assertIn('root.switchPanel(direction)', source)
        self.assertIn('scroll.contentY = servicesPage.y', source)
        services = source[source.index('id: servicesPage'):source.index('// End services')]
        self.assertIn('Existing service policy may move or remove detected files.', services)
        self.assertIn('Confirm existing policy', services)
        self.assertIn('CursorSurface {', source)
        self.assertIn('color: Color.accent', source)
        self.assertIn('if (busy || stale ||', source)
        self.assertIn('if (!root.confirmationCancel) root.request(root.pendingAction)', source)
        self.assertIn('root.cursorItems.length &&', source)


if __name__ == '__main__':
    unittest.main()
