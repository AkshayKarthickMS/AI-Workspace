import fs from "node:fs/promises";
import path from "node:path";

const outputDirectory = path.resolve("data/demo");
const outputFile = path.join(outputDirectory, "sales_data.csv");
const rowCount = 10_000;

let seed = 20260912;
function random() {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 4294967296;
}

function pick(items) {
  return items[Math.floor(random() * items.length)];
}

function weightedPick(items) {
  const total = items.reduce((sum, item) => sum + item.weight, 0);
  let threshold = random() * total;
  for (const item of items) {
    threshold -= item.weight;
    if (threshold <= 0) return item.value;
  }
  return items.at(-1).value;
}

function normal(mean, deviation) {
  const u = Math.max(random(), Number.EPSILON);
  const v = random();
  return mean + deviation * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function clamp(value, lower, upper) {
  return Math.min(Math.max(value, lower), upper);
}

function roundCurrency(value) {
  return Math.round(value * 100) / 100;
}

function csvEscape(value) {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

const products = [
  { name: "Aegis Assist", category: "Collaboration", price: 720, margin: 0.57, weight: 23, inventory: 540 },
  { name: "Aegis Insight", category: "Analytics", price: 1180, margin: 0.59, weight: 22, inventory: 420 },
  { name: "Aegis Automate", category: "Workflow Automation", price: 1450, margin: 0.46, weight: 18, inventory: 310 },
  { name: "Aegis Edge", category: "Infrastructure", price: 950, margin: 0.51, weight: 17, inventory: 270 },
  { name: "Aegis Shield", category: "Security", price: 1320, margin: 0.63, weight: 20, inventory: 360 },
];

const regionProfiles = {
  "North America": {
    countries: ["United States", "Canada"],
    salespeople: ["Morgan Hale", "Riley Chen", "Jordan Brooks", "Taylor Nguyen"],
  },
  Europe: {
    countries: ["United Kingdom", "Germany", "France", "Netherlands"],
    salespeople: ["Alex Mercer", "Sofia Laurent", "Lukas Weber", "Priya Shah"],
  },
  APAC: {
    countries: ["Australia", "Singapore", "Japan", "India"],
    salespeople: ["Mei Tan", "Arjun Kapoor", "Haruto Sato", "Olivia Grant"],
  },
  "Latin America": {
    countries: ["Brazil", "Mexico", "Chile", "Colombia"],
    salespeople: ["Camila Torres", "Diego Ramos", "Valentina Cruz"],
  },
};

const segmentProfiles = [
  { value: "Enterprise", weight: 30, unitMultiplier: 2.6, discount: 0.92 },
  { value: "Mid-Market", weight: 45, unitMultiplier: 1.35, discount: 0.97 },
  { value: "SMB", weight: 25, unitMultiplier: 0.65, discount: 1.03 },
];

const channelProfiles = [
  { value: "Direct", weight: 52, priceMultiplier: 1 },
  { value: "Partner", weight: 30, priceMultiplier: 0.93 },
  { value: "Online", weight: 18, priceMultiplier: 0.97 },
];

function dateFromOffset(offset) {
  const date = new Date(Date.UTC(2023, 0, 1));
  date.setUTCDate(date.getUTCDate() + offset);
  return date;
}

function seasonalMultiplier(month) {
  if (month === 11) return 1.45;
  if (month === 10) return 1.2;
  if (month === 8) return 1.1;
  if (month === 0 || month === 1) return 0.78;
  if (month === 6 || month === 7) return 0.88;
  return 1;
}

function regionForDate(date) {
  const isEuropeDecline = date.getUTCFullYear() === 2025;
  return weightedPick([
    { value: "North America", weight: isEuropeDecline ? 43 : 37 },
    { value: "Europe", weight: isEuropeDecline ? 16 : 29 },
    { value: "APAC", weight: isEuropeDecline ? 27 : 22 },
    { value: "Latin America", weight: 14 },
  ]);
}

function productMargin(product, date) {
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  if (product.name === "Aegis Automate" && (year > 2025 || (year === 2025 && month >= 6))) {
    return 0.68 + normal(0, 0.015);
  }
  if (product.name === "Aegis Edge" && year === 2025) return 0.29 + normal(0, 0.018);
  return product.margin + normal(0, 0.018);
}

const headers = [
  "date",
  "region",
  "country",
  "product",
  "product_category",
  "customer_segment",
  "units_sold",
  "unit_price",
  "revenue",
  "cost",
  "profit",
  "sales_channel",
  "salesperson",
  "inventory_level",
];

const rows = [headers.join(",")];
for (let index = 0; index < rowCount; index += 1) {
  const date = dateFromOffset(Math.floor(random() * 1096));
  const region = regionForDate(date);
  const profile = regionProfiles[region];
  const product = weightedPick(products.map((item) => ({ value: item, weight: item.weight })));
  const segment = weightedPick(segmentProfiles.map((item) => ({ value: item, weight: item.weight })));
  const channel = weightedPick(channelProfiles.map((item) => ({ value: item, weight: item.weight })));
  const month = date.getUTCMonth();
  const isSpike =
    region === "North America" &&
    product.name === "Aegis Insight" &&
    date >= new Date(Date.UTC(2025, 10, 10)) &&
    date <= new Date(Date.UTC(2025, 10, 24));
  const isInventoryConstrained =
    region === "APAC" &&
    product.name === "Aegis Edge" &&
    date >= new Date(Date.UTC(2025, 8, 1)) &&
    date <= new Date(Date.UTC(2025, 10, 30));

  let units = Math.max(1, Math.round(normal(18, 8) * segment.unitMultiplier * seasonalMultiplier(month)));
  if (region === "Europe" && date.getUTCFullYear() === 2025) units = Math.max(1, Math.round(units * 0.74));
  if (isSpike) units = Math.max(1, Math.round(units * 3.8));

  let inventoryLevel = Math.max(units + 4, Math.round(product.inventory + normal(0, 75)));
  if (isInventoryConstrained) {
    inventoryLevel = Math.floor(7 + random() * 24);
    units = Math.min(units, Math.max(1, inventoryLevel - Math.floor(random() * 4)));
  }

  let priceModifier = segment.discount * channel.priceMultiplier * (1 + normal(0, 0.025));
  if (product.name === "Aegis Edge" && date.getUTCFullYear() === 2025) priceModifier *= 0.89;
  const unitPrice = roundCurrency(product.price * clamp(priceModifier, 0.72, 1.12));
  const revenue = roundCurrency(units * unitPrice);
  const margin = clamp(productMargin(product, date), 0.16, 0.78);
  const cost = roundCurrency(revenue * (1 - margin));
  const profit = roundCurrency(revenue - cost);

  rows.push(
    [
      date.toISOString().slice(0, 10),
      region,
      pick(profile.countries),
      product.name,
      product.category,
      segment.value,
      units,
      unitPrice.toFixed(2),
      revenue.toFixed(2),
      cost.toFixed(2),
      profit.toFixed(2),
      channel.value,
      pick(profile.salespeople),
      inventoryLevel,
    ]
      .map(csvEscape)
      .join(","),
  );
}

await fs.mkdir(outputDirectory, { recursive: true });
await fs.writeFile(outputFile, `${rows.join("\n")}\n`, "utf8");
console.log(`Wrote ${rowCount} records to ${outputFile}`);
