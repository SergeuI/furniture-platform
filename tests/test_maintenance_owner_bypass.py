from __future__ import annotations

import re
import tempfile
import unittest
from unittest.mock import patch

import scripts.db_update_wizard as wizard
import scripts.maintenance_owner_bypass as owner_bypass


class MaintenanceOwnerBypassTests(unittest.TestCase):
    def test_render_owner_html_pages_are_placeholder_free(self) -> None:
        access_html = owner_bypass.render_owner_access_html()
        logout_html = owner_bypass.render_owner_logout_html()

        self.assertIn("Власницький доступ активовано", access_html)
        self.assertIn("Власницький доступ завершено", logout_html)
        self.assertIn(f'href="{owner_bypass.OWNER_SITE_URL}"', access_html)
        self.assertIn(f'href="{owner_bypass.OWNER_LOGOUT_URL}"', access_html)
        self.assertIn(f'href="{owner_bypass.OWNER_LOGIN_URL}"', logout_html)
        self.assertNotIn("{{", access_html)
        self.assertNotIn("{{", logout_html)
        self.assertNotIn("token", access_html.lower())
        self.assertNotIn("token", logout_html.lower())

    def test_render_owner_nginx_templates_keep_required_flags_and_escape_token(self) -> None:
        token = 'owner-token-"unsafe".+'
        nginx_map = owner_bypass.render_owner_nginx_map(token)
        nginx_loader = owner_bypass.render_owner_nginx_loader()
        nginx_locations = owner_bypass.render_owner_nginx_locations(token)

        self.assertIn("map $http_cookie $mpfc_maintenance_gate_file", nginx_map)
        self.assertIn("map $remote_user $mpfc_maintenance_owner_set_cookie", nginx_map)
        self.assertEqual(nginx_map.count("map $http_cookie $mpfc_maintenance_gate_file"), 1)
        self.assertEqual(nginx_map.count("map $remote_user $mpfc_maintenance_owner_set_cookie"), 1)
        self.assertIn("default /opt/furniture-maintenance/maintenance.flag;", nginx_map)
        self.assertIn(r'~(?:^|;\\s*)', nginx_map)
        self.assertNotIn("~*", nginx_map)
        self.assertIn('default "";', nginx_map)
        self.assertIn('"mpfc-owner"', nginx_map)
        self.assertIn(
            f'"mpfc_maintenance_owner={re.escape(token)}; Path=/; Max-Age=7200; Secure; HttpOnly; SameSite=Strict"',
            nginx_map,
        )
        self.assertNotIn("$mpfc_maintenance_owner_allowed", nginx_map)
        self.assertNotIn("default 0;", nginx_map)
        self.assertEqual(nginx_loader.strip(), "include /etc/nginx/secure/mpfc-maintenance-owner-map.conf;")
        self.assertIn("location = /__maintenance_owner/login {", nginx_locations)
        self.assertIn("location = /__maintenance_owner/logout {", nginx_locations)
        self.assertIn("alias /var/www/furniture-maintenance/owner-access.html;", nginx_locations)
        self.assertIn("alias /var/www/furniture-maintenance/owner-logout.html;", nginx_locations)
        self.assertIn('auth_basic "MP Furniture Owner Access";', nginx_locations)
        self.assertIn("add_header Set-Cookie $mpfc_maintenance_owner_set_cookie always;", nginx_locations)
        self.assertIn(
            'Set-Cookie "mpfc_maintenance_owner=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict" always;',
            nginx_locations,
        )
        self.assertNotIn("return 302", nginx_locations)
        self.assertIn("Secure", nginx_locations)
        self.assertIn("HttpOnly", nginx_locations)
        self.assertIn("SameSite=Strict", nginx_locations)
        self.assertIn("Path=/", nginx_locations)
        self.assertNotIn(token, nginx_locations)
        self.assertNotIn("{{", nginx_map)
        self.assertNotIn("{{", nginx_locations)
        logout_block = nginx_locations.split("location = /__maintenance_owner/logout {", 1)[1]
        self.assertNotIn("auth_basic", logout_block)
        login_block = nginx_locations.split("location = /__maintenance_owner/login {", 1)[1].split(
            "location = /__maintenance_owner/logout {",
            1,
        )[0]
        self.assertIn("auth_basic", login_block)
        self.assertIn("add_header Set-Cookie $mpfc_maintenance_owner_set_cookie always;", login_block)
        self.assertNotIn('Set-Cookie "mpfc_maintenance_owner=', login_block)

    def test_build_owner_bypass_preview_writes_case_sensitive_gate_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = owner_bypass.build_owner_bypass_preview("CaseSensitiveOwnerToken", temp_dir)
            map_text = bundle["nginx-owner-map.conf"].read_text(encoding="utf-8")
            locations_text = bundle["nginx-owner-locations.conf"].read_text(encoding="utf-8")

        self.assertIn("map $http_cookie $mpfc_maintenance_gate_file", map_text)
        self.assertIn("map $remote_user $mpfc_maintenance_owner_set_cookie", map_text)
        self.assertIn("default /opt/furniture-maintenance/maintenance.flag;", map_text)
        self.assertIn("CaseSensitiveOwnerToken", map_text)
        self.assertIn('default "";', map_text)
        self.assertIn('"mpfc-owner"', map_text)
        self.assertIn("mpfc_maintenance_owner=CaseSensitiveOwnerToken", map_text)
        self.assertNotIn("$mpfc_maintenance_owner_allowed", map_text)
        self.assertNotIn("default 0;", map_text)
        self.assertNotIn("~*", map_text)
        self.assertNotIn("{{", map_text)
        self.assertNotIn("}}", map_text)
        self.assertNotIn("casesensitivetoken", map_text)
        self.assertIn("auth_basic", locations_text)
        self.assertIn("auth_basic_user_file /etc/nginx/secure/mpfc-maintenance-owner.htpasswd;", locations_text)
        self.assertIn("owner-access.html", locations_text)
        self.assertEqual(locations_text.count("Set-Cookie"), 2)
        self.assertEqual(locations_text.count("mpfc_maintenance_owner=CaseSensitiveOwnerToken"), 0)
        self.assertIn("add_header Set-Cookie $mpfc_maintenance_owner_set_cookie always;", locations_text)
        self.assertIn("Path=/", locations_text)
        self.assertIn("Secure", locations_text)
        self.assertIn("HttpOnly", locations_text)
        self.assertIn("SameSite=Strict", locations_text)
        self.assertIn("owner-logout.html", locations_text)
        self.assertIn("mpfc_maintenance_owner=;", locations_text)
        self.assertIn("Max-Age=0", locations_text)
        self.assertIn("Max-Age=7200", map_text)
        self.assertNotIn("return 302", locations_text)
        self.assertNotIn("{{", locations_text)
        self.assertNotIn("}}", locations_text)

    def test_build_owner_bypass_preview_writes_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outputs = owner_bypass.build_owner_bypass_preview("owner-token", temp_dir)
            self.assertEqual(
                sorted(outputs),
                [
                    "nginx-owner-loader.conf",
                    "nginx-owner-locations.conf",
                    "nginx-owner-map.conf",
                    "owner-access.html",
                    "owner-logout.html",
                ],
            )
            for path in outputs.values():
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)
                self.assertNotIn("{{", path.read_text(encoding="utf-8"))

    def test_apply_owner_bypass_to_site_config_rewrites_only_https_block(self) -> None:
        current_config = (
            "server {\n"
            "    listen 80;\n"
            "    server_name mpfc.com.ua www.mpfc.com.ua 45.94.157.42;\n"
            "    return 301 https://$host$request_uri;\n"
            "}\n\n"
            "server {\n"
            "    listen 443 ssl;\n"
            "    server_name mpfc.com.ua www.mpfc.com.ua 45.94.157.42;\n"
            "    ssl_certificate /etc/ssl/cert.pem;\n"
            "    ssl_certificate_key /etc/ssl/key.pem;\n"
            "    location / {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /admin/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /api/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location = /openapi.json {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "}\n"
        )

        transformed = owner_bypass.apply_owner_bypass_to_site_config(current_config)

        self.assertEqual(transformed.count("if (-f /opt/furniture-maintenance/maintenance.flag)"), 0)
        self.assertEqual(transformed.count("$mpfc_maintenance_gate_file"), 4)
        self.assertEqual(
            transformed.count("include /etc/nginx/secure/mpfc-maintenance-owner-locations.conf;"),
            1,
        )
        self.assertIn("return 301 https://$host$request_uri;", transformed)
        self.assertIn("listen 80;", transformed)
        self.assertIn("listen 443 ssl;", transformed)
        self.assertIn("ssl_certificate /etc/ssl/cert.pem;", transformed)
        self.assertIn("ssl_certificate_key /etc/ssl/key.pem;", transformed)
        self.assertEqual(owner_bypass.apply_owner_bypass_to_site_config(transformed), transformed)

    def test_apply_owner_bypass_to_site_config_rejects_wrong_check_count(self) -> None:
        too_few_checks = (
            "server {\n"
            "    listen 80;\n"
            "}\n\n"
            "server {\n"
            "    listen 443 ssl;\n"
            "    location / {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /admin/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /api/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "}\n"
        )
        too_many_checks = (
            "server {\n"
            "    listen 80;\n"
            "}\n\n"
            "server {\n"
            "    listen 443 ssl;\n"
            "    location / {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /admin/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /api/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location = /openapi.json {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "    location /extra/ {\n"
            "        if (-f /opt/furniture-maintenance/maintenance.flag) { return 503; }\n"
            "    }\n"
            "}\n"
        )

        with self.assertRaisesRegex(ValueError, "Expected exactly four maintenance flag checks"):
            owner_bypass.apply_owner_bypass_to_site_config(too_few_checks)
        with self.assertRaisesRegex(ValueError, "Expected exactly four maintenance flag checks"):
            owner_bypass.apply_owner_bypass_to_site_config(too_many_checks)

    def test_product_center_buttons_open_owner_urls(self) -> None:
        dummy = wizard.WizardApp.__new__(wizard.WizardApp)
        with patch.object(wizard.webbrowser, "open") as open_mock:
            wizard.WizardApp.open_maintenance_owner_login(dummy)
            wizard.WizardApp.open_maintenance_owner_logout(dummy)

        self.assertEqual(open_mock.call_args_list[0].args[0], owner_bypass.OWNER_LOGIN_URL)
        self.assertEqual(open_mock.call_args_list[1].args[0], owner_bypass.OWNER_LOGOUT_URL)


if __name__ == "__main__":
    unittest.main()
