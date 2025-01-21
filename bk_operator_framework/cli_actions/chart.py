from importlib import import_module

from bk_operator_framework.cli_actions import echo
from bk_operator_framework.core import crd, template
from bk_operator_framework.core.project import project_desc
from bk_operator_framework.core.webhook import get_webhooks


def main(part):
    echo.info("Writing scaffold for you to edit...")

    project_desc.reload()
    project_desc.create_or_update_chart(part)

    template.create_or_update_chart_basic_file(
        project_desc.project_name, project_desc.chart.version, project_desc.chart.appVersion
    )

    resource_versions_dict = {}
    cluster_role_rule_list = []
    for resource in project_desc.resources:
        if resource.api:
            key = f"{resource.plural}.{resource.group}.{resource.domain}"
            resource_versions_dict.setdefault(key, [])
            resource_schema_module = import_module(
                f"api.{resource.group}.{resource.version}.{resource.singular}_schemas"
            )
            resource_schema_model = getattr(resource_schema_module, resource.kind)
            resource_additional_printer_columns = getattr(resource_schema_module, "ADDITIONAL_PRINTER_COLUMN_LIST")
            openapi_v3_schema = crd.get_openapi_v3_schema(resource_schema_model)
            if not openapi_v3_schema.get("properties", {}).get("status", {}).get("properties"):
                openapi_v3_schema["properties"].pop("status", None)
            resource_versions_dict[key].append(
                {
                    "resource": resource,
                    "openapi_v3_schema": openapi_v3_schema,
                    "additional_printer_columns": resource_additional_printer_columns,
                }
            )
        if resource.controller:
            controller_module = import_module(f"internal.controller.{resource.singular}_controller")
            cluster_role_rule_list.extend(getattr(controller_module, "RBAC_RULE_LIST"))

    for _, resource_versions in resource_versions_dict.items():
        template.create_or_update_chart_crds(resource_versions)

    validating_webhooks, mutating_webhooks = get_webhooks(project_desc.project_name, project_desc.domain, project_desc)

    template.create_or_update_chart_templates(
        project_desc.project_name, cluster_role_rule_list, validating_webhooks, mutating_webhooks
    )

    template.create_chart_values(project_desc.project_name)
