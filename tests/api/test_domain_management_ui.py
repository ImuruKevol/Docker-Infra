import unittest
from pathlib import Path


ROOT = Path("/root/docker-infra/project/main")
DOMAINS_TEMPLATE = ROOT / "src" / "app" / "page.domains" / "view.pug"
DOMAINS_VIEW = ROOT / "src" / "app" / "page.domains" / "view.ts"
DOMAINS_API = ROOT / "src" / "app" / "page.domains" / "api.py"
DOMAINS_MODEL = ROOT / "src" / "model" / "struct" / "domains.py"
DOMAINS_DDNS = ROOT / "src" / "model" / "struct" / "domains_ddns.py"
LOCAL_COMMAND_CATALOG = ROOT / "src" / "model" / "struct" / "local_command_catalog.py"
LOCAL_COMMAND_SCRIPTS = ROOT / "src" / "model" / "struct" / "local_command_scripts.py"
RUNTIME_CONFIG = ROOT / "config" / "docker_infra.py"
SERVICE_NGINX = ROOT / "src" / "model" / "struct" / "service_nginx.py"
SERVICES_PREFLIGHT = ROOT / "src" / "model" / "struct" / "services_preflight.py"
SEARCH_SELECT_TEMPLATE = ROOT / "src" / "app" / "component.search.select" / "view.html"
SEARCH_SELECT_VIEW = ROOT / "src" / "app" / "component.search.select" / "view.ts"


class DomainManagementUiStaticContractTest(unittest.TestCase):
    def test_domain_management_screen_is_ddns_only(self):
        template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        view = DOMAINS_VIEW.read_text(encoding="utf-8")
        api = DOMAINS_API.read_text(encoding="utf-8")
        domains = DOMAINS_MODEL.read_text(encoding="utf-8")

        self.assertIn("DDNS 관리 서버", template)
        self.assertIn("등록된 DDNS 레코드", template)
        self.assertIn("ddnsRegistrations", view)
        self.assertIn("ddns.load()", api)
        self.assertIn('"zones": []', api)
        self.assertIn("def service_options", domains)
        self.assertIn("ddns.service_zone_options", domains)

        for token in [
            "Domain Zones",
            "DNS Records",
            "Zone ID",
            "recordModalOpen",
            "zoneModalOpen",
            "recordDetailModalOpen",
            "syncAllZones",
            "openZoneModal",
            "openRecordModal",
            "save_zone",
            "sync_zone",
            "save_record",
            "delete_record",
            "delete_certificate",
        ]:
            self.assertNotIn(token, template + view + api)

    def test_ddns_management_server_contract_is_wired(self):
        template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        view = DOMAINS_VIEW.read_text(encoding="utf-8")
        api = DOMAINS_API.read_text(encoding="utf-8")
        ddns = DOMAINS_DDNS.read_text(encoding="utf-8")
        local_commands = LOCAL_COMMAND_CATALOG.read_text(encoding="utf-8")
        local_scripts = LOCAL_COMMAND_SCRIPTS.read_text(encoding="utf-8")
        runtime_config = RUNTIME_CONFIG.read_text(encoding="utf-8")
        nginx = SERVICE_NGINX.read_text(encoding="utf-8")
        preflight = SERVICES_PREFLIGHT.read_text(encoding="utf-8")

        self.assertIn("DDNS 서버 API", template)
        self.assertIn("/api/ddns/update", template)
        self.assertIn("*.sub.season.co.kr", template)
        self.assertIn("sub.season.co.kr만 입력하세요", template)
        self.assertIn("ddnsForm.api_url", template)
        self.assertIn("ddnsForm.token_value", template)
        self.assertIn("HTTPS 인증서 검증", template)
        self.assertIn("Dispatcher 요청", template)
        self.assertIn("endpoint.dispatcher?.last_sent_ip", template)
        self.assertNotIn("endpoint.dispatcher?.last_hostname", template)
        self.assertIn("Dispatcher 등록", template)
        self.assertIn("ensureDdnsDispatcher()", template)
        self.assertIn("ddnsDispatcherBadgeClass()", template)
        self.assertEqual(template.count("span DDNS 서버 추가"), 1)
        self.assertIn("table(class=\"w-full min-w-[1360px]", template)
        self.assertIn("th(class=\"w-24 whitespace-nowrap px-4 py-2 text-left font-semibold\") 상태", template)
        dispatcher_header = "th(class=\"w-48 whitespace-nowrap px-4 py-2 text-left font-semibold\") Dispatcher 요청"
        host_header = "th(class=\"w-44 px-4 py-2 text-left font-semibold\") Host"
        ip_header = "th(class=\"w-52 whitespace-nowrap px-4 py-2 text-left font-semibold\") IP"
        registration_header = "th(class=\"w-24 px-4 py-2 text-center font-semibold\") 등록"
        api_header = "th(class=\"px-4 py-2 text-left font-semibold\") DDNS 서버 API"
        for token in [dispatcher_header, host_header, ip_header, registration_header, api_header]:
            self.assertIn(token, template)
        self.assertLess(template.index(dispatcher_header), template.index(host_header))
        self.assertLess(template.index(host_header), template.index(ip_header))
        self.assertLess(template.index(registration_header), template.index(api_header))
        self.assertIn("*.{{endpoint.domain_suffix}}", template)
        self.assertIn("연결 서비스", template)
        self.assertIn("연결 대상", template)
        self.assertIn("th(class=\"w-64 px-4 py-2 text-left font-semibold\") 연결 서비스", template)
        self.assertIn("td(class=\"whitespace-nowrap px-4 py-3 text-center\")", template)
        self.assertIn("min-w-[4rem] justify-center whitespace-nowrap", template)
        self.assertIn("div(class=\"flex flex-nowrap items-center justify-end gap-1 whitespace-nowrap\")", template)
        self.assertIn("[href]=\"registrationHostnameHref(item)\"", template)
        self.assertIn("target=\"_blank\"", template)
        self.assertIn("p(class=\"min-w-0 break-all text-xs font-semibold text-zinc-950 dark:text-zinc-50\") {{item.domain}}", template)
        self.assertIn("ml-2 mr-2 inline-flex h-6 w-6", template)
        self.assertIn("(click)=\"setDdnsRegistrationFilter(endpoint.id)\"", template)
        self.assertIn("[ngClass]=\"ddnsRegistrationFilterClass(endpoint.id)\"", template)
        self.assertIn("filteredDdnsRegistrations().length", template)
        self.assertIn("th(class=\"w-40 whitespace-nowrap px-4 py-2 text-left font-semibold\") 마지막 갱신", template)
        self.assertIn("td(class=\"whitespace-nowrap px-4 py-3 text-xs text-zinc-600 dark:text-zinc-300\") {{formatDate(item.last_sync_at)}}", template)
        self.assertIn("[routerLink]=\"serviceDetailLink(item)\"", template)
        self.assertIn("[routerLink]=\"targetDetailLink(item)\"", template)
        self.assertIn("fa-server", template)
        self.assertNotIn("span 상세", template)
        self.assertIn("endpointRegistrationCount(endpoint)", template)
        self.assertIn("forceUpdateDdnsEndpoint(endpoint)", template)
        self.assertIn("API 호출", template)
        self.assertNotIn('(click)="checkDdnsEndpoint(endpoint)"', template)

        self.assertIn("save_ddns_endpoint", api)
        self.assertIn("force_update_ddns_endpoint", api)
        self.assertIn("ensure_ddns_dispatcher", api)
        self.assertIn("ddns_unavailable", api)
        self.assertIn("api_url", view)
        self.assertIn("forceUpdateDdnsEndpoint", view)
        self.assertIn("ensureDdnsDispatcher", view)
        self.assertIn("ddnsDispatcher", view)
        self.assertIn("ddnsUpdateEndpointId", view)
        self.assertIn("ddnsRegistrationEndpointFilter", view)
        self.assertIn("filteredDdnsRegistrations", view)
        self.assertIn("setDdnsRegistrationFilter", view)
        self.assertIn("ddnsRegistrationFilterClass", view)
        self.assertIn("serviceDetailLink", view)
        self.assertIn("registrationHostnameHref", view)
        self.assertIn("targetDetailLink", view)
        self.assertIn("registrationTargetTitle", view)
        self.assertIn("registrationMetadata", view)
        self.assertIn("target_node_label", view)
        self.assertIn("target_node_host", view)
        self.assertNotIn("서비스 포트", view)
        self.assertNotIn("공개 포트", view)
        self.assertNotIn("checkDdnsEndpoint", view)
        self.assertNotIn("registration_path: endpoint.registration_path", view)
        self.assertNotIn("health_path: endpoint.health_path", view)
        self.assertNotIn("enabled: endpoint.enabled", view)

        self.assertIn("class DomainDdns", ddns)
        self.assertIn("ddns_endpoints", ddns)
        self.assertIn("ddns_registrations", ddns)
        self.assertIn("DDNS_SCHEMA_PENDING", ddns)
        self.assertIn("to_regclass('ddns_endpoints')", ddns)
        self.assertIn("_load_registrations", ddns)
        self.assertIn("sd.metadata AS service_domain_metadata", ddns)
        self.assertIn("target_node_label", ddns)
        self.assertIn("target_node_policy", ddns)
        self.assertIn("LEFT JOIN service_domains sd", ddns)
        self.assertIn("LEFT JOIN nodes n", ddns)
        self.assertIn("def _api_endpoint", ddns)
        self.assertIn("\"api_url\"", ddns)
        self.assertIn('DEFAULT_REGISTRATION_PATH = "/api/ddns/update"', ddns)
        self.assertIn('"X-DDNS-Key"', ddns)
        self.assertNotIn('headers["Authorization"] = f"Bearer {token}"', ddns)
        self.assertIn('"hostname": domain', ddns)
        self.assertIn('"ip": target["host"]', ddns)
        self.assertIn('config.ddns_public_ip_urls', ddns)
        self.assertIn('_lookup_public_ip', ddns)
        self.assertIn('sync_dispatcher', ddns)
        self.assertIn('force_update_endpoint', ddns)
        self.assertIn('dispatcher_status', ddns)
        self.assertIn('ensure_dispatcher', ddns)
        self.assertIn('_dispatcher_summaries', ddns)
        self.assertIn("ddns_management", ddns)
        self.assertIn("register_service_domains", ddns)
        self.assertIn("unregister_service_domains", ddns)
        self.assertIn("def _response_failure", ddns)
        self.assertIn("def _assert_response_ok", ddns)
        self.assertIn("PreserveMethodRedirectHandler", ddns)
        self.assertIn("_existing_registration_current", ddns)
        self.assertIn("_mark_registration_failed", ddns)

        self.assertIn("ddns.dispatcher.ensure", local_commands)
        self.assertIn("/etc/NetworkManager/dispatcher.d/90-docker-infra-ddns", local_commands)
        self.assertIn("DDNS_DISPATCHER_AGENT_SCRIPT", local_scripts)
        self.assertIn("last_sent_ip", local_scripts)
        self.assertIn("last_sent_at", local_scripts)
        self.assertIn("--endpoint-id", local_scripts)
        self.assertIn('"X-DDNS-Key": token', local_scripts)
        self.assertIn("DOCKER_INFRA_DDNS_PUBLIC_IP_URLS", runtime_config)
        self.assertIn("DOCKER_INFRA_PUBLIC_IPV4", runtime_config)
        self.assertIn("def public_dns_address", runtime_config)
        self.assertIn("ddns.dispatcher.ensure", runtime_config)
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
