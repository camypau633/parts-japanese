"""Canonical CatCar Japanese catalog roots and brand aliases.

A catalog root is not always a single vehicle marque: Toyota/Lexus and
Nissan/Infiniti share CatCar catalog endpoints. Brand identity must therefore
remain unresolved until the page itself provides an explicit discriminator.
"""

CATCAR_JAPANESE_CATALOGS = {
    "toyota": {
        "url": "https://www.catcar.info/toyota/",
        "brands": ["Toyota", "Lexus"],
        "detail_adapter": "toyota",
    },
    "nissan": {
        "url": "https://www.catcar.info/nissan/",
        "brands": ["Nissan", "Infiniti"],
        "detail_adapter": "nissan",
    },
    "honda": {
        "url": "https://www.catcar.info/honda/",
        "brands": ["Honda"],
        "detail_adapter": "honda",
    },
    "suzuki": {
        "url": "https://www.catcar.info/suzuki/",
        "brands": ["Suzuki"],
        "detail_adapter": None,
    },
    "mazda": {
        "url": "https://www.catcar.info/mazda/",
        "brands": ["Mazda"],
        "detail_adapter": None,
    },
    "mitsubishi": {
        "url": "https://www.catcar.info/mitsubishi/",
        "brands": ["Mitsubishi"],
        "detail_adapter": None,
    },
    "isuzu": {
        "url": "https://www.catcar.info/isuzu/",
        "brands": ["Isuzu"],
        "detail_adapter": None,
    },
    "subaru": {
        "url": "https://www.catcar.info/subaru/",
        "brands": ["Subaru"],
        "detail_adapter": None,
    },
}


def catalog_config(make):
    key = (make or "").strip().lower()
    if key not in CATCAR_JAPANESE_CATALOGS:
        raise ValueError("unsupported CatCar Japanese catalog: " + key)
    return CATCAR_JAPANESE_CATALOGS[key]
