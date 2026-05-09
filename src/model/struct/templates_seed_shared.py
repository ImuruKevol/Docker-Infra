import textwrap


SEED_VERSION = "2026-05-09-service-ux-v4-swarm-internal-dns"


def schema(title, description, fields, required=None):
    properties = {}
    for item in fields:
        properties[item["name"]] = {
            "title": item["title"],
            "type": item.get("type", "string"),
            "description": item.get("description", ""),
            "default": item.get("default"),
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "description": description,
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def readme(title, summary, web_port, services):
    lines = [
        f"# {title}",
        "",
        summary,
        "",
        f"- 도메인 연결 포트: `{web_port}`",
        f"- 포함 구성: {', '.join(services)}",
        "",
        "이 템플릿은 웹 서비스와 내부 DB/캐시가 함께 동작하도록 구성되어 있습니다.",
        "도메인은 웹 서비스 포트에 연결하고, DB/캐시는 외부로 노출하지 않습니다.",
        "",
    ]
    return "\n".join(lines)


def metadata(category, image, components, public_endpoint=None, component_labels=None, generated_secrets=None):
    return {
        "category": category,
        "primary_image": image,
        "seed_version": SEED_VERSION,
        "domain_ready": True,
        "components": components,
        "public_endpoint": public_endpoint or {},
        "component_labels": component_labels or {},
        "generated_secrets": generated_secrets or [],
    }


def base_fields(namespace, web_image, web_port):
    return [
        {"name": "namespace", "title": "서비스 내부 이름", "default": namespace},
        {"name": "web_image", "title": "웹 이미지", "default": web_image},
        {"name": "service_port", "title": "연결 포트", "type": "integer", "default": web_port},
    ]


def block(text):
    return textwrap.dedent(text).strip() + "\n"


Model = type(
    "TemplatesSeedShared",
    (),
    {
        "schema": staticmethod(schema),
        "readme": staticmethod(readme),
        "metadata": staticmethod(metadata),
        "base_fields": staticmethod(base_fields),
        "block": staticmethod(block),
    },
)()
