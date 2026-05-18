import unittest
from pathlib import Path


ROOT = Path("/root/docker-infra/project/main")
DOMAINS_TEMPLATE = ROOT / "src" / "app" / "page.domains" / "view.pug"
DOMAINS_VIEW = ROOT / "src" / "app" / "page.domains" / "view.ts"
DOMAINS_CLOUDFLARE = ROOT / "src" / "model" / "struct" / "domains_cloudflare.py"
DOMAINS_DDNS = ROOT / "src" / "model" / "struct" / "domains_ddns.py"
SERVICE_NGINX = ROOT / "src" / "model" / "struct" / "service_nginx.py"
SERVICES_PREFLIGHT = ROOT / "src" / "model" / "struct" / "services_preflight.py"
SEARCH_SELECT_TEMPLATE = ROOT / "src" / "app" / "component.search.select" / "view.html"
SEARCH_SELECT_VIEW = ROOT / "src" / "app" / "component.search.select" / "view.ts"


class DomainManagementUiStaticContractTest(unittest.TestCase):
    def test_domain_records_use_compact_content_and_detail_modal(self):
        template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        view = DOMAINS_VIEW.read_text(encoding="utf-8")

        self.assertIn("recordDetailModalOpen", template)
        self.assertIn("openRecordDetail(record)", template)
        self.assertIn("contentSummary(record)", template)
        self.assertIn("Name 또는 Content 검색", template)
        self.assertIn("query: ''", view)
        self.assertIn("filters.query", view)
        self.assertNotIn("recordFilters.name", view)
        self.assertNotIn("recordFilters.content", view)
        self.assertNotIn("Exposure", template)
        self.assertNotIn("Cloudflare Proxy 사용", template)
        self.assertNotIn("Priority", template)
        self.assertNotIn("레코드 타입 안내", template)
        self.assertNotIn("Domain 설정", template)

    def test_record_type_toggle_and_hidden_dns_defaults_are_wired(self):
        template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        view = DOMAINS_VIEW.read_text(encoding="utf-8")
        cloudflare = DOMAINS_CLOUDFLARE.read_text(encoding="utf-8")

        self.assertIn('(click)="setRecordType(type)"', template)
        self.assertIn("recordNameHelper()", template)
        self.assertIn("DEFAULT_TTL_BY_TYPE", view)
        self.assertIn("proxied: false", view)
        self.assertIn("DEFAULT_TTL_BY_TYPE", cloudflare)
        self.assertIn("PROXIED_CAPABLE_TYPES", cloudflare)
        self.assertIn('cf_payload["proxied"] = False', cloudflare)
        self.assertIn("DEFAULT_PRIORITY_BY_TYPE", cloudflare)

    def test_certificate_service_links_open_service_detail(self):
        template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        view = DOMAINS_VIEW.read_text(encoding="utf-8")

        self.assertIn("serviceDetailHref(item)", template)
        self.assertIn("fa-arrow-right", template)
        self.assertIn("상세", template)
        self.assertIn("/services?service_id=", view)

    def test_ddns_management_server_is_separate_from_cloudflare_zone_flow(self):
        template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        view = DOMAINS_VIEW.read_text(encoding="utf-8")
        api = (ROOT / "src" / "app" / "page.domains" / "api.py").read_text(encoding="utf-8")
        ddns = DOMAINS_DDNS.read_text(encoding="utf-8")
        nginx = SERVICE_NGINX.read_text(encoding="utf-8")
        preflight = SERVICES_PREFLIGHT.read_text(encoding="utf-8")

        self.assertIn("DDNS 관리 서버", template)
        self.assertIn("DDNS 서버 API", template)
        self.assertIn("*.sub.season.co.kr", template)
        self.assertIn("sub.season.co.kr만 입력하세요", template)
        self.assertIn("ddnsForm.api_url", template)
        self.assertIn("ddnsForm.token_value", template)
        self.assertIn("HTTPS 인증서 검증", template)
        self.assertIn("자체 서명/사설 인증서", template)
        self.assertNotIn("API Base URL", template)
        self.assertNotIn("등록/갱신 경로", template)
        self.assertNotIn("Health 경로", template)
        self.assertNotIn("서비스 도메인 선택에 사용", template)
        self.assertNotIn("ddnsForm.registration_path", template)
        self.assertNotIn("ddnsForm.health_path", template)
        self.assertNotIn("ddnsForm.enabled", template)
        self.assertNotIn('(click)="checkDdnsEndpoint(endpoint)"', template)
        self.assertIn("save_ddns_endpoint", api)
        self.assertIn("ddns_unavailable", api)
        self.assertIn("api_url", view)
        self.assertNotIn("checkDdnsEndpoint", view)
        self.assertNotIn("registration_path: endpoint.registration_path", view)
        self.assertNotIn("health_path: endpoint.health_path", view)
        self.assertNotIn("enabled: endpoint.enabled", view)
        self.assertIn("ddnsEndpoints", view)
        self.assertIn("ddnsWarning", view)
        self.assertIn("ddnsWarning()", template)
        self.assertIn("class DomainDdns", ddns)
        self.assertIn("ddns_endpoints", ddns)
        self.assertIn("ddns_registrations", ddns)
        self.assertIn("DDNS_SCHEMA_PENDING", ddns)
        self.assertIn("to_regclass('ddns_endpoints')", ddns)
        self.assertIn("def _api_endpoint", ddns)
        self.assertIn("\"api_url\"", ddns)
        self.assertIn("ddns_management", ddns)
        self.assertIn("register_service_domains", ddns)
        self.assertIn("unregister_service_domains", ddns)
        self.assertNotIn("_split_domains", nginx)
        self.assertIn("ddns_model.register_service_domains", nginx)
        self.assertIn("ddns_managed", nginx)
        self.assertIn("DDNS 관리 서버 등록", preflight)

    def test_search_select_applies_selection_on_first_click(self):
        template = SEARCH_SELECT_TEMPLATE.read_text(encoding="utf-8")
        view = SEARCH_SELECT_VIEW.read_text(encoding="utf-8")

        self.assertIn('(mousedown)="selectItem(item, $event)"', template)
        self.assertIn('(click)="stopEvent($event, true)"', template)
        self.assertIn('(keydown.enter)="selectItem(item, $event)"', template)
        self.assertIn("stopImmediatePropagation", view)
        self.assertIn("@Input() value: any = ''", view)
        self.assertIn("this.value = this.itemValue(item)", view)
        self.assertIn("this.valueChange.emit(this.value)", view)
        self.assertIn("this.cdr.detectChanges()", view)


if __name__ == "__main__":
    unittest.main()
