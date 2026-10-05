TASKS = {
    "export_order_skus.py": {"label": "SKU от неизпратени поръчки", "dry_run": False, "batch": False, "writes": False},
    "sync.py": {"label": "Синхронизирай наличности и дати", "dry_run": True, "batch": False, "writes": True},
    "import_products.py": {"label": "Качи нови продукти (AI)", "dry_run": True, "batch": True, "writes": True},
    "sync_weight.py": {"label": "Синхронизирай теглото", "dry_run": True, "batch": False, "writes": True},
    "export_missing_skus.py": {"label": "Експортирай липсващи SKU-та", "dry_run": False, "batch": False, "writes": False},
    "find_variations.py": {"label": "Намери вариации", "dry_run": False, "batch": False, "writes": False},
}

TASK_ALIASES = {"sync_metafield.py": "sync.py"}
