import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "../..");

const sources = [
  { size: 16, file: "branding/icons/favicon-16.png" },
  { size: 32, file: "branding/icons/favicon-32.png" },
  { size: 48, file: "branding/icons/favicon-48.png" },
];

const images = await Promise.all(
  sources.map(async (source) => ({
    ...source,
    data: await readFile(path.join(root, source.file)),
  })),
);

const headerSize = 6;
const entrySize = 16;
const directorySize = headerSize + images.length * entrySize;
let offset = directorySize;

const chunks = [];
const header = Buffer.alloc(headerSize);
header.writeUInt16LE(0, 0);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(images.length, 4);
chunks.push(header);

for (const image of images) {
  const entry = Buffer.alloc(entrySize);
  entry.writeUInt8(image.size === 256 ? 0 : image.size, 0);
  entry.writeUInt8(image.size === 256 ? 0 : image.size, 1);
  entry.writeUInt8(0, 2);
  entry.writeUInt8(0, 3);
  entry.writeUInt16LE(1, 4);
  entry.writeUInt16LE(32, 6);
  entry.writeUInt32LE(image.data.length, 8);
  entry.writeUInt32LE(offset, 12);
  chunks.push(entry);
  offset += image.data.length;
}

for (const image of images) {
  chunks.push(image.data);
}

await writeFile(path.join(root, "branding/icons/favicon.ico"), Buffer.concat(chunks));
console.log("favicon.ico generated");
