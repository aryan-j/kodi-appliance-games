from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_APP = ROOT / "resources" / "companion" / "web-ui-app"


class OverlayConnectorContractTests(unittest.TestCase):
    def test_kodi_launcher_passes_logo_artwork_to_overlay(self):
        source = (ROOT / "resources" / "lib" / "launch_service.py").read_text(encoding="utf-8")
        self.assertIn('"--logo"', source)
        self.assertIn('session["logo"]', source)
        self.assertNotIn('"--poster"', source)
        self.assertNotIn('session["cover"]', source)

    def test_webview_payload_exposes_logo_url_not_poster_url(self):
        source = (ROOT / "resources" / "companion" / "WebOverlayForm.cs").read_text(encoding="utf-8")
        self.assertIn('MapArtwork(core, "logo.local", logo)', source)
        self.assertIn('{ "logoUrl", ArtworkUrl("logo.local", logo) }', source)
        self.assertIn('window.overlayUI.updateDynamicState(', source)
        self.assertNotIn('"posterUrl"', source)
        self.assertNotIn('"poster.local"', source)
        self.assertNotIn('"fanart.local"', source)
        self.assertNotIn('"fanartUrl"', source)

    def test_frontend_contains_contained_game_logo_and_normalized_snapshot(self):
        app = (WEB_APP / "src" / "app.jsx").read_text(encoding="utf-8")
        bridge = (WEB_APP / "src" / "bridge.js").read_text(encoding="utf-8")
        styles = (WEB_APP / "src" / "styles.css").read_text(encoding="utf-8")
        contract = (WEB_APP / "src" / "connector-contract.js").read_text(encoding="utf-8")
        self.assertIn("game-logo-image", app)
        self.assertIn("safeLogo(value)", bridge)
        self.assertIn("object-fit: contain", styles)
        self.assertIn("normalizeSnapshot", contract)
        self.assertNotIn("posterUrl", bridge)

    def test_production_markup_has_no_design_gallery_or_hidden_background_work(self):
        markup = (WEB_APP / "index.html").read_text(encoding="utf-8")
        app = (WEB_APP / "src" / "app.jsx").read_text(encoding="utf-8")
        bridge = (WEB_APP / "src" / "bridge.js").read_text(encoding="utf-8")
        self.assertNotIn("states-gallery", markup)
        self.assertNotIn("background-art", markup)
        self.assertNotIn("safeArtwork", bridge)
        self.assertNotIn("fanartUrl", bridge)
        self.assertNotIn("posterUrl", app)

    def test_interactions_use_composited_motion_only(self):
        styles = (WEB_APP / "src" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("backdrop-filter: blur", styles)
        self.assertIn("transition: background-color", styles)
        self.assertIn("transform: translateY", styles)
        self.assertNotIn("transition: box-shadow", styles)
        self.assertNotIn("transition: filter", styles)

    def test_build_source_is_static_and_connector_neutral(self):
        package = (WEB_APP / "package.json").read_text(encoding="utf-8")
        docs = (WEB_APP / "CONNECTORS.md").read_text(encoding="utf-8")
        playnite = (WEB_APP / "src" / "connectors" / "playnite.js").read_text(encoding="utf-8")
        kodi = (WEB_APP / "src" / "connectors" / "kodi.js").read_text(encoding="utf-8")
        self.assertIn('"build": "vite build && node scripts/sync-output.mjs"', package)
        self.assertIn("Playnite", docs)
        self.assertIn("Kodi", docs)
        self.assertIn("no network requests", docs.lower())
        self.assertIn("TotalPlaytime", playnite)
        self.assertIn("ActivatedTime", playnite)
        self.assertIn("normalizeKodiSnapshot", kodi)

    def test_playnite_side_has_real_named_pipe_transport(self):
        root = ROOT / "resources" / "playnite-connector"
        plugin = (root / "src" / "GameApplianceOverlay.Playnite" / "PlayniteOverlayPlugin.cs").read_text(encoding="utf-8")
        server = (root / "src" / "GameApplianceOverlay.Playnite" / "PlayniteOverlayPipeServer.cs").read_text(encoding="utf-8")
        host = (ROOT / "resources" / "companion" / "OverlayPipeClient.cs").read_text(encoding="utf-8")
        self.assertIn("OnGameStarted", plugin)
        self.assertIn("OnGameStopped", plugin)
        self.assertIn("NamedPipeServerStream", server)
        self.assertIn("PipeSecurity", server)
        self.assertIn("PipeAccessRights.FullControl", server)
        self.assertIn('"--pipe-token"', plugin)
        self.assertIn("NamedPipeClientStream", host)
        self.assertIn('"type", "hello"', host)
        self.assertIn("SendAction", host)


if __name__ == "__main__":
    unittest.main()
