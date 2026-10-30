"""Modifications appliquées au composant Overkiz amont pour produire local_tahoma.

Chaque transformation travaille sur le texte d'un fichier amont et vérifie que
son ancre existe exactement une fois : si Home Assistant refactore le code visé,
la synchronisation échoue avec un message précis au lieu de produire un
composant silencieusement faux.

Pour ajuster une modification après un changement amont, éditer uniquement ce
fichier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

NEW_DOMAIN = "local_tahoma"
OLD_DOMAIN = "overkiz"
NAME = "Overkiz (Local)"
SUFFIX = " (Local)"
REPO_URL = "https://github.com/farsightbs/ha-local-tahoma"


class TransformError(RuntimeError):
    """Une ancre amont est introuvable ou ambiguë."""


def replace_once(text: str, old: str, new: str, *, where: str) -> str:
    count = text.count(old)
    if count != 1:
        raise TransformError(
            f"{where}: ancre trouvée {count} fois (attendu 1) :\n---\n{old}\n---"
        )
    return text.replace(old, new)


# --------------------------------------------------------------------------- #
# Fichiers Python
# --------------------------------------------------------------------------- #


def const_py(text: str) -> str:
    # Le domaine sert de préfixe aux identifiants d'appareils, au registre des
    # entités, aux services et aux clés de traduction (translation_key=DOMAIN).
    return replace_once(
        text,
        f'DOMAIN: Final = "{OLD_DOMAIN}"',
        f'DOMAIN: Final = "{NEW_DOMAIN}"',
        where="const.py",
    )


def init_py(text: str) -> str:
    where = "__init__.py"
    # Plus d'import automatique des identifiants OAuth2 Rexel (cloud).
    text = replace_once(
        text,
        "from homeassistant.components.application_credentials import (\n"
        "    ClientCredential,\n"
        "    async_import_client_credential,\n"
        ")\n",
        "",
        where=where,
    )
    text = replace_once(
        text,
        "    # Auto-import Rexel's fixed public OAuth2 client (PKCE, no secret).\n"
        "    await async_import_client_credential(\n"
        "        hass,\n"
        "        DOMAIN,\n"
        '        ClientCredential(REXEL_OAUTH_CLIENT_ID, "", name="Rexel"),\n'
        "    )\n"
        "\n",
        "",
        where=where,
    )
    # Une entrée sans api_type est traitée comme locale.
    text = replace_once(
        text,
        "api_type = entry.data.get(CONF_API_TYPE, APIType.CLOUD)",
        "api_type = entry.data.get(CONF_API_TYPE, APIType.LOCAL)",
        where=where,
    )
    # Passerelle : nom suffixé.
    text = replace_once(
        text,
        "name=gateway.type.beautify_name if gateway.type else gateway.id,",
        'name=f"{gateway.type.beautify_name if gateway.type else gateway.id}'
        f'{SUFFIX}",',
        where=where,
    )
    text = replace_once(
        text,
        "            name=gateway_id,\n",
        f'            name=f"{{gateway_id}}{SUFFIX}",\n',
        where=where,
    )
    return text


def entity_py(text: str) -> str:
    # Nom d'appareil suffixé : l'entity_id (appareil + nom d'entité) hérite
    # donc de « _local » et le nom affiché de « (Local) ».
    return replace_once(
        text,
        "            name=self.device.label,\n",
        f'            name=f"{{self.device.label}}{SUFFIX}",\n',
        where="entity.py",
    )


def config_flow_py(text: str) -> str:
    where = "config_flow.py"
    text = replace_once(
        text,
        "_api_type: APIType = APIType.CLOUD",
        "_api_type: APIType = APIType.LOCAL",
        where=where,
    )
    # L'étape initiale mène directement à la saisie locale. L'ancienne étape
    # reste dans la classe sous un autre nom (code mort, ignoré par HA).
    text = replace_once(
        text,
        "    @override\n"
        "    async def async_step_user(\n"
        "        self, user_input: dict[str, Any] | None = None\n"
        "    ) -> ConfigFlowResult:\n"
        '        """Handle the initial step via config flow."""\n',
        "    @override\n"
        "    async def async_step_user(\n"
        "        self, user_input: dict[str, Any] | None = None\n"
        "    ) -> ConfigFlowResult:\n"
        '        """Local only: go straight to the local API step."""\n'
        "        return await self.async_step_local()\n"
        "\n"
        "    async def _upstream_async_step_user(\n"
        "        self, user_input: dict[str, Any] | None = None\n"
        "    ) -> ConfigFlowResult:\n"
        '        """Handle the initial step via config flow (unused upstream code)."""\n',
        where=where,
    )
    # Titre de l'entrée de configuration.
    text = replace_once(
        text,
        "return self.async_create_entry(title=title, data=user_input)",
        f'return self.async_create_entry(title=f"{{title}}{SUFFIX}", data=user_input)',
        where=where,
    )
    return text


def services_py(text: str) -> str:
    # Les services sont enregistrés sous DOMAIN : rien à changer, mais on
    # vérifie l'hypothèse pour détecter un éventuel changement amont.
    if "DOMAIN" not in text:
        raise TransformError("services.py: DOMAIN n'est plus utilisé")
    return text


# --------------------------------------------------------------------------- #
# Fichiers de données
# --------------------------------------------------------------------------- #


def services_yaml(text: str) -> str:
    return replace_once(
        text,
        f"integration: {OLD_DOMAIN}",
        f"integration: {NEW_DOMAIN}",
        where="services.yaml",
    )


def _rename_entity_translation_keys(data: dict, where: str) -> None:
    """Les entités climate/water_heater utilisent translation_key=DOMAIN."""
    entity = data.get("entity", {})
    renamed = 0
    for platform_keys in entity.values():
        if OLD_DOMAIN in platform_keys:
            platform_keys[NEW_DOMAIN] = platform_keys.pop(OLD_DOMAIN)
            renamed += 1
    if not renamed:
        raise TransformError(f"{where}: aucune clé entity.*.{OLD_DOMAIN} trouvée")


def icons_json(text: str) -> str:
    data = json.loads(text)
    _rename_entity_translation_keys(data, "icons.json")
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def strings_json(text: str) -> str:
    data = json.loads(text)
    _rename_entity_translation_keys(data, "strings.json")
    config = data["config"]
    flow_title = config["flow_title"]
    if "{gateway_id}" not in flow_title:
        raise TransformError("strings.json: flow_title inattendu")
    config["flow_title"] = flow_title.replace(
        "{gateway_id}", f"{{gateway_id}}{SUFFIX}"
    )
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def manifest_json(text: str) -> str:
    data = json.loads(text)
    if data.get("domain") != OLD_DOMAIN:
        raise TransformError("manifest.json: domaine amont inattendu")
    version = (Path(__file__).parent / "VERSION").read_text().strip()

    zeroconf = [z for z in data.get("zeroconf", []) if z["type"] == "_kizboxdev._tcp.local."]
    if not zeroconf:
        raise TransformError("manifest.json: zeroconf _kizboxdev introuvable")

    deps = [d for d in data.get("dependencies", []) if d != "application_credentials"]

    new = {
        "domain": NEW_DOMAIN,
        "name": NAME,
        "codeowners": [],
        "config_flow": True,
        "dependencies": deps,
        "documentation": REPO_URL,
        "integration_type": data.get("integration_type", "hub"),
        "iot_class": "local_polling",
        "issue_tracker": f"{REPO_URL}/issues",
        "loggers": data.get("loggers", []),
        "requirements": data["requirements"],
        "version": version,
        # Seule la découverte du mode développeur (API locale) est conservée ;
        # DHCP et _kizbox._tcp restent à l'intégration officielle.
        "zeroconf": zeroconf,
    }
    return json.dumps(new, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- #
# Traductions
# --------------------------------------------------------------------------- #

COMMON_KEYS = {
    "common::config_flow::abort::already_configured_account": "Account is already configured",
    "common::config_flow::abort::oauth2_missing_configuration": "The component is not configured. Please follow the documentation.",
    "common::config_flow::data::api_token": "API token",
    "common::config_flow::data::host": "Host",
    "common::config_flow::data::password": "Password",
    "common::config_flow::data::username": "Username",
    "common::config_flow::data::verify_ssl": "Verify SSL certificate",
    "common::config_flow::error::cannot_connect": "Failed to connect",
    "common::config_flow::error::invalid_auth": "Invalid authentication",
    "common::config_flow::error::unknown": "Unexpected error",
    "common::config_flow::title::oauth2_pick_implementation": "Pick authentication method",
    "common::state::auto": "Auto",
    "common::state::closed": "Closed",
    "common::state::full": "Full",
    "common::state::low": "Low",
    "common::state::manual": "Manual",
    "common::state::medium": "Medium",
    "common::state::normal": "Normal",
    "common::state::not_home": "Away",
    "common::state::open": "Open",
    "common::state::very_low": "Very low",
    "component::cover::entity_component::_::state_attributes::speed::state::fast": "Fast",
    "component::cover::entity_component::_::state_attributes::speed::state::slow": "Slow",
    "component::climate::entity_component::_::state_attributes::hvac_action::state::cooling": "Cooling",
    "component::climate::entity_component::_::state_attributes::hvac_action::state::heating": "Heating",
}

_KEY_RE = re.compile(r"\[%key:([^%]+)%\]")


def resolve_references(strings: dict, warn: Callable[[str], None]) -> dict:
    """Résout les [%key:…%] de strings.json, absents des composants custom."""

    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in COMMON_KEYS:
            return COMMON_KEYS[key]
        # Référence vers une autre section de notre propre composant.
        own = f"component::{NEW_DOMAIN}::"
        if key.startswith(f"component::{OLD_DOMAIN}::"):
            key = own + key[len(f"component::{OLD_DOMAIN}::"):]
        if key.startswith(own):
            node = strings
            for part in key[len(own):].split("::"):
                node = node.get(part) if isinstance(node, dict) else None
            if isinstance(node, str) and not _KEY_RE.search(node):
                return node
        last = key.rsplit("::", 1)[-1].replace("_", " ")
        warn(f"référence de traduction inconnue {key!r} -> {last!r}")
        return last.capitalize()

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            return _KEY_RE.sub(sub, node)
        return node

    return walk(strings)


# --------------------------------------------------------------------------- #
# Table des fichiers
# --------------------------------------------------------------------------- #

TEXT_TRANSFORMS: dict[str, Callable[[str], str]] = {
    "const.py": const_py,
    "__init__.py": init_py,
    "entity.py": entity_py,
    "config_flow.py": config_flow_py,
    "services.py": services_py,
    "services.yaml": services_yaml,
    "icons.json": icons_json,
    "manifest.json": manifest_json,
}

# strings.json est traité à part (transformation + génération de translations/en.json).
STRINGS = "strings.json"

# Fichiers amont non repris (OAuth2 cloud / identifiants d'application).
EXCLUDED = {"application_credentials.py", "quality_scale.yaml", "strings.json"}
