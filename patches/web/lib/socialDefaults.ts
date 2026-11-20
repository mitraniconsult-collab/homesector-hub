export type Brand = { id: string; name: string; website: string; instagram: string; facebook: string; tiktok: string; pinterest: string; collectorUrls: string[]; enabled: boolean };

export const defaultBrands: Brand[] = [
  { id: "atmosphera", name: "Atmosphera", website: "https://www.atmosphera.com/", instagram: "", facebook: "", tiktok: "", pinterest: "", collectorUrls: ["https://www.atmosphera.com/en/"], enabled: true },
  { id: "5five", name: "5five", website: "https://www.5five.com/", instagram: "https://www.instagram.com/5fivesimplysmart/", facebook: "", tiktok: "", pinterest: "", collectorUrls: ["https://www.5five.com/"], enabled: true },
  { id: "hesperide", name: "Hespéride", website: "https://www.hesperide.com/", instagram: "", facebook: "", tiktok: "", pinterest: "", collectorUrls: ["https://www.hesperide.com/en/new/new.html"], enabled: true },
  { id: "secret-de-gourmet", name: "Secret de Gourmet", website: "https://www.secretdegourmet.com/", instagram: "", facebook: "", tiktok: "", pinterest: "", collectorUrls: ["https://www.secretdegourmet.com/"], enabled: true },
];
