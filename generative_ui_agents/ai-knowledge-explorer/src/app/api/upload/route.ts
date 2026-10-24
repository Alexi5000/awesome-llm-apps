import { NextRequest, NextResponse } from "next/server";
import { writeFile, mkdtemp } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

// NOTE: Python agent reads from the same tmpdir — only works when both processes run on the same host.
const UPLOAD_DIR = join(tmpdir(), "knowledge-explorer-uploads");

export async function POST(req: NextRequest) {
  const { files } = await req.json();
  if (!Array.isArray(files) || files.length === 0 || files.length > 20 ||
      files.some((file: unknown) => !file || typeof file !== "object" ||
        !("name" in file) || typeof file.name !== "string" || file.name.length > 255 ||
        !("content" in file) || typeof file.content !== "string")) {
    return NextResponse.json({ error: "Provide 1 to 20 named text files" }, { status: 400 });
  }
  if (files.reduce((total: number, file: { content: string }) =>
      total + Buffer.byteLength(file.content, "utf8"), 0) > 10 * 1024 * 1024) {
    return NextResponse.json({ error: "Files exceed 10 MB" }, { status: 413 });
  }
  const directory = await mkdtemp(`${UPLOAD_DIR}-`);

  const saved: { name: string; path: string }[] = [];
  for (const file of files) {
    const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, "_");
    const path = join(directory, `${saved.length}-${safeName}`);
    await writeFile(path, file.content, { encoding: "utf-8", flag: "wx", mode: 0o600 });
    saved.push({ name: file.name, path });
  }

  return NextResponse.json({ files: saved });
}
