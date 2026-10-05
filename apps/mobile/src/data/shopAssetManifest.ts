export interface ShopLogoAsset {
  brandId: number
  brandName: string
  objectKey: string
  aliases: readonly string[]
}

export interface ResolvedShopLogo {
  brandId: number
  brandName: string
  imageKey: string
  uri: string | null
}

const ASSET_BASE_URL = process.env.EXPO_PUBLIC_ASSET_BASE_URL?.replace(/\/+$/, '') ?? ''

/**
 * Shop logos stored in R2. The numeric prefix is a stable logo catalogue id;
 * it is deliberately independent from location.location_id because one brand
 * can have many physical locations.
 */
export const SHOP_LOGOS: readonly ShopLogoAsset[] = [
  { brandId: 1, brandName: '99 Speedmart', objectKey: 'shop/01_99_speedmart.webp', aliases: ['99 SPEEDMART', '99 SPEED MART'] },
  { brandId: 2, brandName: 'Econsave', objectKey: 'shop/02_econsave.webp', aliases: ['ECONSAVE', 'ECON SAVE'] },
  { brandId: 3, brandName: 'Giant', objectKey: 'shop/03_giant.webp', aliases: ['GIANT'] },
  { brandId: 4, brandName: 'Mydin', objectKey: 'shop/04_mydin.webp', aliases: ['MYDIN'] },
  { brandId: 5, brandName: 'AEON', objectKey: 'shop/05_aeon.webp', aliases: ['AEON', 'JUSCO'] },
  { brandId: 6, brandName: 'TF Value-Mart', objectKey: 'shop/06_tf_value_mart.webp', aliases: ['TF VALUE MART', 'TF VALUEMART'] },
  { brandId: 7, brandName: 'Segi Fresh', objectKey: 'shop/07_segi_fresh_segi_cash_and_carry.webp', aliases: ['SEGI FRESH', 'SEGI CASH AND CARRY', 'SEGI CASH CARRY', 'SEGI'] },
  { brandId: 8, brandName: 'Servay', objectKey: 'shop/08_servay.webp', aliases: ['SERVAY'] },
  { brandId: 9, brandName: "Lotus's", objectKey: 'shop/09_lotuss.webp', aliases: ['LOTUSS', 'LOTUS'] },
  { brandId: 10, brandName: 'Pantai Timur', objectKey: 'shop/10_pantai_timor_timur.webp', aliases: ['PANTAI TIMUR', 'PANTAI TIMOR'] },
  { brandId: 11, brandName: 'Bataras', objectKey: 'shop/11_bataras.webp', aliases: ['BATARAS'] },
  { brandId: 12, brandName: 'Tunas Manja', objectKey: 'shop/12_tunas_manja.webp', aliases: ['TUNAS MANJA'] },
  { brandId: 13, brandName: 'G-Mart', objectKey: 'shop/13_g_mart_gmart.webp', aliases: ['G MART', 'GMART'] },
  { brandId: 14, brandName: 'Tesco', objectKey: 'shop/14_tesco.webp', aliases: ['TESCO'] },
  { brandId: 15, brandName: 'Everwin', objectKey: 'shop/15_everwin.webp', aliases: ['EVERWIN'] },
  { brandId: 16, brandName: 'Billion', objectKey: 'shop/16_billion.webp', aliases: ['BILLION'] },
  { brandId: 17, brandName: 'The Store', objectKey: 'shop/17_the_store.webp', aliases: ['THE STORE'] },
  { brandId: 18, brandName: 'TMG', objectKey: 'shop/18_tmg.webp', aliases: ['TMG'] },
  { brandId: 19, brandName: 'Treleaf', objectKey: 'shop/19_treleaf.webp', aliases: ['TRELEAF'] },
  { brandId: 20, brandName: 'CCK Fresh Mart', objectKey: 'shop/20_cck_fresh_mart.webp', aliases: ['CCK FRESH MART', 'CCK'] },
  { brandId: 21, brandName: 'Econo Jaya', objectKey: 'shop/21_econo_jaya_econjaya.webp', aliases: ['ECONO JAYA', 'ECONJAYA'] },
  { brandId: 22, brandName: 'NSK', objectKey: 'shop/22_nsk.webp', aliases: ['NSK'] },
  { brandId: 23, brandName: 'PKT', objectKey: 'shop/23_pkt.webp', aliases: ['PKT'] },
  { brandId: 24, brandName: 'Village Grocer', objectKey: 'shop/24_village_grocer.webp', aliases: ['VILLAGE GROCER'] },
  { brandId: 25, brandName: 'Maslee', objectKey: 'shop/25_maslee.webp', aliases: ['MASLEE'] },
  { brandId: 26, brandName: 'WLS Enterprise', objectKey: 'shop/26_wls_enterprise.webp', aliases: ['WLS ENTERPRISE', 'WLS'] },
  { brandId: 27, brandName: 'CKS', objectKey: 'shop/27_cks.webp', aliases: ['CKS'] },
  { brandId: 28, brandName: 'Doremart', objectKey: 'shop/28_doremart.webp', aliases: ['DOREMART', 'DORE MART'] },
  { brandId: 29, brandName: 'Emart', objectKey: 'shop/29_emart.webp', aliases: ['EMART', 'E MART'] },
  { brandId: 30, brandName: 'Hero Market', objectKey: 'shop/30_hero_market.webp', aliases: ['HERO MARKET'] },
  { brandId: 31, brandName: '88 Fresh Mart', objectKey: 'shop/31_88_fresh_mart.webp', aliases: ['88 FRESH MART'] },
  { brandId: 32, brandName: 'LYC', objectKey: 'shop/32_lyc.webp', aliases: ['LYC'] },
  { brandId: 33, brandName: 'Salamku', objectKey: 'shop/33_salamku.webp', aliases: ['SALAMKU'] },
  { brandId: 34, brandName: 'Well Mart', objectKey: 'shop/34_well_mart.webp', aliases: ['WELL MART', 'WELLMART'] },
  { brandId: 35, brandName: 'C-Mart', objectKey: 'shop/35_c_mart.webp', aliases: ['C MART'] },
  { brandId: 36, brandName: 'Jaya Grocer', objectKey: 'shop/36_jaya_grocer.webp', aliases: ['JAYA GROCER'] },
  { brandId: 37, brandName: 'Mercato', objectKey: 'shop/37_mercato.webp', aliases: ['MERCATO'] },
  { brandId: 38, brandName: 'Nirwana Maju', objectKey: 'shop/38_nirwana_maju.webp', aliases: ['NIRWANA MAJU'] },
  { brandId: 39, brandName: 'Pacific', objectKey: 'shop/39_pacific.webp', aliases: ['PACIFIC'] },
  { brandId: 40, brandName: 'City Fresh Mart', objectKey: 'shop/40_city_fresh_mart.webp', aliases: ['CITY FRESH MART'] },
  { brandId: 41, brandName: 'JMS', objectKey: 'shop/41_jms.webp', aliases: ['JMS'] },
  { brandId: 42, brandName: 'Nam Leong', objectKey: 'shop/42_nam_leong.webp', aliases: ['NAM LEONG'] },
  { brandId: 43, brandName: 'Save Mini Market', objectKey: 'shop/43_save_mini_market.webp', aliases: ['SAVE MINI MARKET'] },
  { brandId: 44, brandName: 'Target', objectKey: 'shop/44_target.webp', aliases: ['TARGET'] },
  { brandId: 45, brandName: 'Family Store', objectKey: 'shop/45_family_store.webp', aliases: ['FAMILY STORE'] },
  { brandId: 46, brandName: 'Hwa Thai', objectKey: 'shop/46_hwa_thai.webp', aliases: ['HWA THAI'] },
  { brandId: 47, brandName: 'LePaPa', objectKey: 'shop/47_lepapa.webp', aliases: ['LEPAPA', 'LE PAPA'] },
  { brandId: 48, brandName: 'Milimewa', objectKey: 'shop/48_milimewa.webp', aliases: ['MILIMEWA'] },
  { brandId: 49, brandName: 'TY Pasaraya', objectKey: 'shop/49_ty_pasaraya.webp', aliases: ['TY PASARAYA'] },
  { brandId: 50, brandName: 'Home-U', objectKey: 'shop/50_home_u.webp', aliases: ['HOME U', 'HOMEU'] },
  { brandId: 51, brandName: 'LS Mart', objectKey: 'shop/51_ls_mart.webp', aliases: ['LS MART'] },
  { brandId: 52, brandName: 'Sabasun', objectKey: 'shop/52_sabasun.webp', aliases: ['SABASUN'] },
  { brandId: 53, brandName: 'Bestamart', objectKey: 'shop/53_bestamart.webp', aliases: ['BESTAMART', 'BESTA MART'] },
  { brandId: 54, brandName: 'Darussalam', objectKey: 'shop/54_darussalam.webp', aliases: ['DARUSSALAM'] },
  { brandId: 55, brandName: 'Everrise', objectKey: 'shop/55_everrise.webp', aliases: ['EVERRISE'] },
  { brandId: 56, brandName: 'Farley', objectKey: 'shop/56_farley.webp', aliases: ['FARLEY'] },
  { brandId: 57, brandName: 'Fresco', objectKey: 'shop/57_fresco.webp', aliases: ['FRESCO'] },
  { brandId: 58, brandName: 'Gentingmas', objectKey: 'shop/58_gentingmas.webp', aliases: ['GENTINGMAS', 'GENTING MAS'] },
  { brandId: 59, brandName: 'Jumbo Grocer', objectKey: 'shop/59_jumbo_grocer.webp', aliases: ['JUMBO GROCER'] },
  { brandId: 60, brandName: 'MDS Mart', objectKey: 'shop/60_mds_mart.webp', aliases: ['MDS MART', 'MDS'] },
  { brandId: 61, brandName: 'Megamart', objectKey: 'shop/61_megamart.webp', aliases: ['MEGAMART', 'MEGA MART'] },
  { brandId: 62, brandName: 'Sabindo', objectKey: 'shop/62_sabindo.webp', aliases: ['SABINDO'] },
  { brandId: 63, brandName: 'Sinyin', objectKey: 'shop/63_sinyin.webp', aliases: ['SINYIN', 'SIN YIN'] },
  { brandId: 64, brandName: 'TL Mart', objectKey: 'shop/64_tl_mart.webp', aliases: ['TL MART'] },
  { brandId: 65, brandName: 'XR Mart', objectKey: 'shop/65_xr_mart.webp', aliases: ['XR MART'] },
  { brandId: 66, brandName: 'Alief Maju', objectKey: 'shop/66_alief_maju.webp', aliases: ['ALIEF MAJU'] },
  { brandId: 67, brandName: 'Choon Cheong', objectKey: 'shop/67_choon_cheong.webp', aliases: ['CHOON CHEONG'] },
  { brandId: 68, brandName: 'Cold Storage', objectKey: 'shop/68_cold_storage.webp', aliases: ['COLD STORAGE'] },
  { brandId: 69, brandName: 'CS Mini Market', objectKey: 'shop/69_cs_mini_market.webp', aliases: ['CS MINI MARKET'] },
  { brandId: 70, brandName: 'Darul Makmur', objectKey: 'shop/70_darul_makmur.webp', aliases: ['DARUL MAKMUR'] },
  { brandId: 71, brandName: 'Grand Union', objectKey: 'shop/71_grand_union.webp', aliases: ['GRAND UNION'] },
  { brandId: 72, brandName: 'Instar Superfresh', objectKey: 'shop/72_instar_superfresh.webp', aliases: ['INSTAR SUPERFRESH', 'INSTAR'] },
  { brandId: 73, brandName: 'KIP Mart', objectKey: 'shop/73_kip_mart.webp', aliases: ['KIP MART'] },
  { brandId: 74, brandName: 'Shakri', objectKey: 'shop/74_shakri.webp', aliases: ['SHAKRI'] },
  { brandId: 75, brandName: 'Upwell', objectKey: 'shop/75_upwell.webp', aliases: ['UPWELL'] },
]

function normalizeShopName(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/&/g, ' AND ')
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}

function containsWholeAlias(locationName: string, alias: string): boolean {
  return ` ${locationName} `.includes(` ${alias} `)
}

/** Find the logo definition for a physical location's display name. */
export function shopLogoForLocationName(locationName: string | null | undefined): ShopLogoAsset | null {
  if (!locationName?.trim()) return null

  const normalizedLocationName = normalizeShopName(locationName)

  return SHOP_LOGOS.find(shop =>
    shop.aliases.some(alias => containsWholeAlias(normalizedLocationName, normalizeShopName(alias))),
  ) ?? null
}

export function shopLogoUriForKey(imageKey: string): string | null {
  return ASSET_BASE_URL ? `${ASSET_BASE_URL}/${imageKey}` : null
}

/** Resolve both the stable R2 key and its public URI for a location name. */
export function shopLogoForLocation(locationName: string | null | undefined): ResolvedShopLogo | null {
  const shop = shopLogoForLocationName(locationName)
  if (!shop) return null

  return {
    brandId: shop.brandId,
    brandName: shop.brandName,
    imageKey: shop.objectKey,
    uri: shopLogoUriForKey(shop.objectKey),
  }
}
