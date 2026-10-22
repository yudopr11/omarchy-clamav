"""Static QML wiring checks; these do not replace live focus/rendering checks."""
from pathlib import Path
import unittest


PANEL = Path(__file__).resolve().parents[1] / "Panel.qml"


class PanelTabsTests(unittest.TestCase):
    def test_pages_and_cursor_scope(self):
        source = PANEL.read_text()
        for page, controls in {
            "overview": ["refreshButton", "installButton", "helperInstallButton", "logButton"],
            "services": ["daemonStart", "daemonStop", "daemonBoot", "daemonDisableBoot", "scannerStart", "scannerStop", "scannerBoot", "updaterStart", "updaterStop", "updaterBoot"],
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
        self.assertIn('Existing on-access command/policy', services)
        self.assertIn('Confirm existing policy', services)
        self.assertIn('CursorSurface {', source)
        self.assertIn('color: Color.accent', source)
        self.assertIn('if (busy || stale ||', source)
        self.assertIn('if (!root.confirmationCancel) root.request(root.pendingAction)', source)
        self.assertIn('root.cursorItems.length &&', source)


if __name__ == '__main__':
    unittest.main()
