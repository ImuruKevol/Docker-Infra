import unittest
from pathlib import Path


ROOT = Path("/root/docker-infra/project/main")
DOMAINS_TEMPLATE = ROOT / "src" / "app" / "page.domains" / "view.pug"
DOMAINS_VIEW = ROOT / "src" / "app" / "page.domains" / "view.ts"
DOMAINS_CLOUDFLARE = ROOT / "src" / "model" / "struct" / "domains_cloudflare.py"
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
