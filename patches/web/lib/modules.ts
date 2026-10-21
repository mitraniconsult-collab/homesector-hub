export type HubModule = {
  id: string;
  href: string;
  label: string;
  description: string;
  status: "ready" | "phase1" | "planned";
};

export const modules: HubModule[] = [
  { id: "easyrea", href: "/easyrea", label: "Easyrea Sync", description: "Синхронизации, импорт, вариации, отчети и история.", status: "phase1" },
  { id: "logistics", href: "/logistics", label: "Logistics", description: "Shopify пратки и Speedy / Econt / Sameday статуси.", status: "phase1" },
  { id: "social", href: "/social", label: "Social", description: "Brand Collector, Content Feed, Drafts и publishing pipeline.", status: "phase1" },
  { id: "shopify", href: "/shopify", label: "Shopify Operations", description: "Inventory, публикации, translations и cleanup проверки.", status: "planned" },
  { id: "feeds", href: "/feeds", label: "Feeds", description: "Фийдове по пазар, XML прегледи и отчети.", status: "phase1" },
  { id: "reports", href: "/reports", label: "Reports", description: "Общи отчети, job history и грешки.", status: "planned" }
];

export const easyreaTasks = [
  { key: "export_order_skus.py", name: "SKU от неизпратени поръчки", cadence: "преди заявка", duration: "според броя поръчки", writes: false, dryRun: false },
  { key: "sync.py", name: "Синхронизирай наличности и дати", cadence: "при нужда", duration: "според броя промени", writes: true, dryRun: true },
  { key: "import_products.py", name: "Качи нови продукти (AI)", cadence: "при нужда", duration: "според новите продукти", writes: true, dryRun: true },
  { key: "sync_weight.py", name: "Синхронизирай теглото", cadence: "еднократно", duration: "~75 мин", writes: true, dryRun: true },
  { key: "export_missing_skus.py", name: "Експортирай липсващи SKU-та", cadence: "при нужда", duration: "според броя варианти", writes: false, dryRun: false },
  { key: "find_variations.py", name: "Намери вариации", cadence: "при нужда", duration: "~10 мин", writes: false, dryRun: false }
];
