import {
  Upload,
  Layers,
  Ghost,
  FileStack,
  ShieldCheck,
  BarChart3,
  Receipt,
  MapPinned,
  FileSpreadsheet,
  Hash,
  Trash2,
  type LucideIcon,
} from "lucide-react";

// Stages with a dedicated page to navigate into once unlocked. Every other
// stage is a placeholder until it's ported (see docs/ROADMAP.md).
export const STAGE_ROUTES: Record<string, string> = {
  load_data: "load-data",
  datenmodell: "datenmodell",
  geisterobjekte: "geisterobjekte",
  sap_carp: "sap-carp",
  quality: "quality",
  report: "report",
  tax_cleansing: "tax-cleansing",
  address_cleansing: "address-cleansing",
  sap_template: "sap-template",
  register_clean: "register-cleansing",
  delete: "delete-records",
};

export const STAGE_ICONS: Record<string, LucideIcon> = {
  load_data: Upload,
  datenmodell: Layers,
  geisterobjekte: Ghost,
  sap_carp: FileStack,
  quality: ShieldCheck,
  report: BarChart3,
  tax_cleansing: Receipt,
  address_cleansing: MapPinned,
  sap_template: FileSpreadsheet,
  register_clean: Hash,
  delete: Trash2,
};
