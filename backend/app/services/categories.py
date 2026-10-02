from typing import Dict, List


CATEGORIES: List[Dict[str, str]] = [
    {
        "id": 1,
        "name": "Fondamentaux de la cybersécurité",
        "family": "Fondamentaux",
    },
    {
        "id": 2,
        "name": "Architecture et conception sécurisées",
        "family": "Fondamentaux",
    },
    {
        "id": 3,
        "name": "Sensibilisation et formation à la cybersécurité",
        "family": "Fondamentaux",
    },
    {
        "id": 4,
        "name": "Sécurité physique",
        "family": "Fondamentaux",
    },
    {
        "id": 5,
        "name": "Gestion des risques",
        "family": "Fondamentaux",
    },
    {
        "id": 6,
        "name": "Réseaux et protocoles",
        "family": "Réseaux",
    },
    {
        "id": 7,
        "name": "Sécurité réseau",
        "family": "Réseaux",
    },
    {
        "id": 8,
        "name": "Sécurité Wi-Fi et réseaux sans fil",
        "family": "Réseaux",
    },
    {
        "id": 9,
        "name": "Sécurité des emails",
        "family": "Réseaux",
    },
    {
        "id": 10,
        "name": "API et services",
        "family": "Réseaux",
    },
    {
        "id": 11,
        "name": "Sécurité des systèmes",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 12,
        "name": "Sécurité Windows",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 13,
        "name": "Sécurité Linux",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 14,
        "name": "Active Directory et environnements Microsoft",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 15,
        "name": "Sécurité des environnements virtualisés",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 16,
        "name": "Conteneurs et Kubernetes",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 17,
        "name": "Sécurité matérielle et firmware",
        "family": "Systèmes & infrastructures",
    },
    {
        "id": 18,
        "name": "Sécurité Web et applications",
        "family": "Applications & développement",
    },
    {
        "id": 19,
        "name": "DevSecOps et sécurité du développement",
        "family": "Applications & développement",
    },
    {
        "id": 20,
        "name": "Vulnérabilités et gestion des correctifs",
        "family": "Applications & développement",
    },
    {
        "id": 21,
        "name": "Sécurité de la chaîne d'approvisionnement",
        "family": "Applications & développement",
    },
    {
        "id": 22,
        "name": "Reverse engineering",
        "family": "Applications & développement",
    },
    {
        "id": 23,
        "name": "Authentification et contrôle d'accès",
        "family": "Identité & données",
    },
    {
        "id": 24,
        "name": "Identité et gestion des accès (IAM)",
        "family": "Identité & données",
    },
    {
        "id": 25,
        "name": "Cryptographie",
        "family": "Identité & données",
    },
    {
        "id": 26,
        "name": "Sécurité des mots de passe et secrets",
        "family": "Identité & données",
    },
    {
        "id": 27,
        "name": "Sécurité des bases de données",
        "family": "Identité & données",
    },
    {
        "id": 28,
        "name": "Protection des données et vie privée",
        "family": "Identité & données",
    },
    {
        "id": 29,
        "name": "Sécurité du cloud",
        "family": "Technologies spécialisées",
    },
    {
        "id": 30,
        "name": "Sécurité mobile",
        "family": "Technologies spécialisées",
    },
    {
        "id": 31,
        "name": "IoT et systèmes embarqués",
        "family": "Technologies spécialisées",
    },
    {
        "id": 32,
        "name": "Sécurité industrielle / OT / SCADA",
        "family": "Technologies spécialisées",
    },
    {
        "id": 33,
        "name": "Sécurité des systèmes embarqués et automobiles",
        "family": "Technologies spécialisées",
    },
    {
        "id": 34,
        "name": "Malwares et logiciels malveillants",
        "family": "Menaces & attaques",
    },
    {
        "id": 35,
        "name": "Phishing et ingénierie sociale",
        "family": "Menaces & attaques",
    },
    {
        "id": 36,
        "name": "OSINT et reconnaissance",
        "family": "Menaces & attaques",
    },
    {
        "id": 37,
        "name": "Exploitation et post-exploitation",
        "family": "Menaces & attaques",
    },
    {
        "id": 38,
        "name": "MITRE ATT&CK et techniques d'attaque",
        "family": "Menaces & attaques",
    },
    {
        "id": 39,
        "name": "Tests d'intrusion et Red Team",
        "family": "Sécurité offensive",
    },
    {
        "id": 40,
        "name": "Sécurité offensive",
        "family": "Sécurité offensive",
    },
    {
        "id": 41,
        "name": "CTF et exercices de cybersécurité",
        "family": "Sécurité offensive",
    },
    {
        "id": 42,
        "name": "Détection, surveillance et SOC",
        "family": "Sécurité défensive",
    },
    {
        "id": 43,
        "name": "SIEM et analyse des logs",
        "family": "Sécurité défensive",
    },
    {
        "id": 44,
        "name": "Threat Intelligence",
        "family": "Sécurité défensive",
    },
    {
        "id": 45,
        "name": "Réponse aux incidents",
        "family": "Sécurité défensive",
    },
    {
        "id": 46,
        "name": "Forensics et analyse numérique",
        "family": "Sécurité défensive",
    },
    {
        "id": 47,
        "name": "Sécurité défensive",
        "family": "Sécurité défensive",
    },
    {
        "id": 48,
        "name": "Gouvernance et politiques de sécurité",
        "family": "Organisation & continuité",
    },
    {
        "id": 49,
        "name": "Normes, conformité et réglementation",
        "family": "Organisation & continuité",
    },
    {
        "id": 50,
        "name": "Continuité d'activité et reprise après sinistre",
        "family": "Organisation & continuité",
    },
]


CATEGORY_BY_ID = {
    category["id"]: category
    for category in CATEGORIES
}


CATEGORY_BY_NAME = {
    category["name"]: category
    for category in CATEGORIES
}


def get_all_categories() -> List[Dict[str, str]]:
    """Retourne les 50 catégories autorisées."""
    return CATEGORIES.copy()


def get_category_by_id(category_id: int) -> Dict[str, str] | None:
    """Retourne une catégorie à partir de son ID."""
    return CATEGORY_BY_ID.get(category_id)


def get_category_by_name(category_name: str) -> Dict[str, str] | None:
    """Retourne une catégorie à partir de son nom."""
    return CATEGORY_BY_NAME.get(category_name)


def get_category_names() -> List[str]:
    """Retourne uniquement les noms des 50 catégories."""
    return [category["name"] for category in CATEGORIES]


def get_categories_by_family(family: str) -> List[Dict[str, str]]:
    """Retourne les catégories appartenant à une famille."""
    return [
        category
        for category in CATEGORIES
        if category["family"] == family
    ]