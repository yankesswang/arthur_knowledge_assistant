import { FileSystemAdapter, MarkdownView, Notice, Platform, TFile } from "obsidian";
import type SubstackPlugin from "../main";

// ─── types ───────────────────────────────────────────────────────────────────

type NodeRequireLike = (id: string) => unknown;
type RequireContainer = typeof globalThis & { require?: NodeRequireLike };

interface McpRuntimeConfig {
	command: string;
	args: string[];
	env: Record<string, string>;
}

interface JsonRpcRequest {
	jsonrpc: "2.0";
	id: number;
	method: string;
	params?: unknown;
}

interface JsonRpcResponse {
	jsonrpc: "2.0";
	id: number;
	result?: unknown;
	error?: { code: number; message: string };
}

type ChildStdoutChunk = Buffer | string;

const PLAYWRIGHT_TOKEN_ENV = "PLAYWRIGHT_MCP_EXTENSION_TOKEN";
const MCP_REQUEST_TIMEOUT_MS = 30_000;
const MCP_NAVIGATE_TIMEOUT_MS = 60_000;
const MCP_EVALUATE_TIMEOUT_MS = 120_000;
const FRONTMATTER_RE = /^---\n[\s\S]*?\n---\n*/;

// ─── public entry ─────────────────────────────────────────────────────────────

export async function uploadToSubstackDraft(plugin: SubstackPlugin): Promise<void> {
	if (!Platform.isDesktopApp) {
		new Notice("Substack upload is only available in the desktop app.");
		return;
	}

	const substackUrl = plugin.settings.substackUrl;
	if (!substackUrl) {
		new Notice("Please set your Substack URL in Settings → Substack in Obsidian.");
		return;
	}

	const view = plugin.app.workspace.getActiveViewOfType(MarkdownView);
	if (!view?.file) {
		new Notice("Open a Markdown note first.");
		return;
	}

	const file = view.file;
	const rawContent = view.editor.getValue();

	try {
		new Notice("Connecting to browser…");
		const payload = await buildPayload(plugin, file, rawContent);
		const runtime = buildRuntime(plugin);
		const client = await StdioMcpClient.connect(runtime);
		try {
			new Notice("Opening Substack editor…");
			await runSubstackPublish(client, payload, substackUrl);
			new Notice("Draft saved to Substack! Open your browser to review and publish.");
			appendLog(plugin, "upload.success", { file: file.path });
		} finally {
			client.close();
		}
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		new Notice(`Upload failed: ${msg}`);
		appendLog(plugin, "upload.error", { file: file.path, error: msg });
	}
}

// ─── payload builder ──────────────────────────────────────────────────────────

interface PublishPayload {
	title: string;
	subtitle: string;
	htmlBody: string;
	coverBase64: string | null;
	coverMime: string | null;
}

async function buildPayload(
	plugin: SubstackPlugin,
	file: TFile,
	raw: string,
): Promise<PublishPayload> {
	// Strip frontmatter
	let md = plugin.settings.stripFrontmatter ? raw.replace(FRONTMATTER_RE, "").trimStart() : raw;

	// Extract title from # heading or use filename
	let title = "";
	const headingMatch = md.match(/^#\s+(.+)$/m);
	if (headingMatch?.[1]) {
		title = headingMatch[1].trim();
		md = md.replace(/^#\s+.+\n?/m, "").trimStart();
	} else if (plugin.settings.useFilenameAsTitle) {
		title = file.basename;
	}

	// Extract subtitle from frontmatter
	const frontmatterMatch = raw.match(/^---\n([\s\S]*?)\n---/);
	let subtitle = "";
	let coverSrc = "";
	if (frontmatterMatch) {
		const fm = frontmatterMatch[1] ?? "";
		const subtitleMatch = fm.match(/^(?:subtitle|description):\s*(.+)$/im);
		if (subtitleMatch?.[1]) subtitle = subtitleMatch[1].trim().replace(/^["']|["']$/g, "");
		// Support formatter.cover or cover
		const coverMatch = fm.match(/cover:\s*(.+)$/im);
		if (coverMatch?.[1]) coverSrc = coverMatch[1].trim();
	}

	// Render markdown → HTML using Obsidian's renderer
	const { htmlBody } = await renderMarkdown(plugin, file, md);

	// Resolve cover image to base64 (if local wikilink)
	let coverBase64: string | null = null;
	let coverMime: string | null = null;
	if (coverSrc) {
		const result = await resolveCoverImage(plugin, file, coverSrc);
		coverBase64 = result.base64;
		coverMime = result.mime;
	}

	return { title, subtitle, htmlBody, coverBase64, coverMime };
}

async function renderMarkdown(
	plugin: SubstackPlugin,
	file: TFile,
	md: string,
): Promise<{ htmlBody: string }> {
	const { MarkdownRenderer, Component } = await import("obsidian");
	const container = document.createElement("div");
	const comp = new Component();
	comp.load();
	await MarkdownRenderer.render(plugin.app, md, container, file.path, comp);
	comp.unload();
	// Strip class and style attributes
	container.querySelectorAll("[class]").forEach((el) => el.removeAttribute("class"));
	container.querySelectorAll("[style]").forEach((el) => el.removeAttribute("style"));
	return { htmlBody: container.innerHTML };
}

async function resolveCoverImage(
	plugin: SubstackPlugin,
	file: TFile,
	coverSrc: string,
): Promise<{ base64: string | null; mime: string | null }> {
	try {
		// Wikilink: ![[image.png]]
		const wikilinkMatch = coverSrc.match(/^!\[\[(.+)\]\]$/);
		const name = wikilinkMatch?.[1] ?? coverSrc;
		const linked = plugin.app.metadataCache.getFirstLinkpathDest(name, file.path);
		if (linked) {
			const buf = await plugin.app.vault.readBinary(linked);
			const ext = linked.extension.toLowerCase();
			const mime =
				ext === "jpg" || ext === "jpeg" ? "image/jpeg" :
				ext === "png" ? "image/png" :
				ext === "gif" ? "image/gif" :
				ext === "webp" ? "image/webp" : "image/png";
			const b64 = arrayBufferToBase64(buf);
			return { base64: b64, mime };
		}
	} catch {
		// ignore, cover is optional
	}
	return { base64: null, mime: null };
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
	const bytes = new Uint8Array(buf);
	let binary = "";
	for (let i = 0; i < bytes.byteLength; i++) {
		binary += String.fromCharCode(bytes[i] ?? 0);
	}
	return btoa(binary);
}

// ─── Playwright automation ────────────────────────────────────────────────────

async function runSubstackPublish(
	client: StdioMcpClient,
	payload: PublishPayload,
	substackUrl: string,
): Promise<void> {
	const editorUrl = `${substackUrl}/publish/post`;

	// Navigate
	await client.callTool("browser_navigate", { url: editorUrl }, MCP_NAVIGATE_TIMEOUT_MS);
	await client.callTool("browser_wait_for", { time: 3000 });

	// Upload cover image first (if any) — Substack shows the upload button near the top
	if (payload.coverBase64 && payload.coverMime) {
		await client.callTool(
			"browser_evaluate",
			{ function: buildCoverUploadFn(payload.coverBase64, payload.coverMime) },
			MCP_EVALUATE_TIMEOUT_MS,
		);
		await client.callTool("browser_wait_for", { time: 2000 });
	}

	// Fill title, subtitle, body via browser evaluate
	const result = await client.callTool(
		"browser_evaluate",
		{ function: buildFillEditorFn(payload.title, payload.subtitle, payload.htmlBody) },
		MCP_EVALUATE_TIMEOUT_MS,
	);

	if (result && typeof result === "object" && "ok" in result && !result.ok) {
		throw new Error((result as Record<string, unknown>).error as string ?? "Editor fill failed");
	}

	// Wait for auto-save (Substack auto-saves drafts)
	await client.callTool("browser_wait_for", { time: 2000 });
}

// Builds the JS function string that fills Substack's editor
function buildFillEditorFn(title: string, subtitle: string, htmlBody: string): string {
	const escapedTitle = JSON.stringify(title);
	const escapedSubtitle = JSON.stringify(subtitle);
	const escapedHtml = JSON.stringify(htmlBody);

	return `async () => {
  try {
    // ── helpers ──────────────────────────────────────────────
    function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

    function findByPlaceholder(...phrases) {
      for (const phrase of phrases) {
        const lower = phrase.toLowerCase();
        for (const el of document.querySelectorAll('[placeholder],[data-placeholder],[aria-placeholder]')) {
          const ph = (el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || el.getAttribute('aria-placeholder') || '').toLowerCase();
          if (ph.includes(lower)) return el;
        }
        // also try by label text in nearby elements
        for (const el of document.querySelectorAll('[contenteditable="true"]')) {
          const prev = el.previousElementSibling;
          if (prev && prev.textContent && prev.textContent.toLowerCase().includes(lower)) return el;
        }
      }
      return null;
    }

    function setContent(el, text) {
      el.focus();
      // Select all and replace
      document.execCommand('selectAll', false);
      document.execCommand('delete', false);
      document.execCommand('insertText', false, text);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function pasteHtml(el, html) {
      el.focus();
      const dt = new DataTransfer();
      dt.setData('text/html', html);
      dt.setData('text/plain', el.textContent || '');
      el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    }

    // ── title ────────────────────────────────────────────────
    const title = ${escapedTitle};
    if (title) {
      await wait(500);
      const titleEl = findByPlaceholder('title')
        || document.querySelector('h1[contenteditable]')
        || document.querySelector('[data-testid="post-title-input"]')
        || document.querySelector('.post-title [contenteditable]');
      if (titleEl) {
        setContent(titleEl, title);
        await wait(300);
      }
    }

    // ── subtitle ─────────────────────────────────────────────
    const subtitle = ${escapedSubtitle};
    if (subtitle) {
      const subtitleEl = findByPlaceholder('subtitle', 'description')
        || document.querySelector('[data-testid="post-subtitle-input"]')
        || document.querySelector('.post-subtitle [contenteditable]');
      if (subtitleEl) {
        setContent(subtitleEl, subtitle);
        await wait(300);
      }
    }

    // ── body ─────────────────────────────────────────────────
    const htmlBody = ${escapedHtml};
    // Find the main body editor (ProseMirror or Draft.js)
    const bodyEl = document.querySelector('.ProseMirror')
      || document.querySelector('.DraftEditor-editorContainer [contenteditable]')
      || document.querySelector('[data-contents="true"]')
      || (() => {
        // Fallback: find largest contenteditable that isn't title/subtitle
        const all = [...document.querySelectorAll('[contenteditable="true"]')];
        return all.sort((a, b) => b.clientHeight - a.clientHeight)[0] || null;
      })();

    if (!bodyEl) return { ok: false, error: 'Could not find body editor' };

    bodyEl.focus();
    await wait(300);

    // Try clipboard paste (most reliable for rich text editors)
    pasteHtml(bodyEl, htmlBody);
    await wait(500);

    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}`;
}

function buildCoverUploadFn(base64: string, mime: string): string {
	return `async () => {
  try {
    function wait(ms) { return new Promise(r => setTimeout(r, ms)); }
    function base64ToBlob(b64, mime) {
      const bin = atob(b64);
      const arr = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      return new Blob([arr], { type: mime });
    }

    const blob = base64ToBlob(${JSON.stringify(base64)}, ${JSON.stringify(mime)});
    const file = new File([blob], 'cover.${mime.split('/')[1] ?? 'png'}', { type: ${JSON.stringify(mime)} });
    const dt = new DataTransfer();
    dt.items.add(file);

    // Find cover image input
    const coverBtn = document.querySelector('[data-testid="cover-image-input"]')
      || document.querySelector('input[type="file"][accept*="image"]')
      || document.querySelector('[aria-label*="cover" i] input[type="file"]');
    if (!coverBtn) return { ok: false, error: 'Cover upload input not found' };

    Object.defineProperty(coverBtn, 'files', { value: dt.files });
    coverBtn.dispatchEvent(new Event('change', { bubbles: true }));
    await wait(3000);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}`;
}

// ─── runtime config ───────────────────────────────────────────────────────────

function buildRuntime(plugin: SubstackPlugin): McpRuntimeConfig {
	const token = plugin.settings.playwrightToken.trim().replace(/^PLAYWRIGHT_MCP_EXTENSION_TOKEN=/i, "");

	// Try to find npx full path for Electron environments
	const npxPath = resolveNpxPath();

	return {
		command: npxPath,
		args: ["-y", "@playwright/mcp@latest", "--extension"],
		env: { [PLAYWRIGHT_TOKEN_ENV]: token },
	};
}

function resolveNpxPath(): string {
	try {
		const req = getNodeRequire();
		const fs = req("node:fs") as typeof import("node:fs");
		const candidates = [
			"/opt/homebrew/bin/npx",
			"/usr/local/bin/npx",
			"/usr/bin/npx",
		];
		for (const p of candidates) {
			if (fs.existsSync(p)) return p;
		}
	} catch {
		// fall back to bare command
	}
	return "npx";
}

// ─── MCP client ───────────────────────────────────────────────────────────────

class StdioMcpClient {
	private nextId = 1;
	private pending = new Map<number, { resolve: (v: JsonRpcResponse) => void; reject: (e: unknown) => void }>();
	private buffer = "";
	private readonly stderrChunks: string[] = [];
	private closed = false;
	private spawnError: Error | null = null;
	private stdinError: Error | null = null;

	private constructor(
		private readonly proc: import("node:child_process").ChildProcessWithoutNullStreams,
	) {}

	static async connect(runtime: McpRuntimeConfig): Promise<StdioMcpClient> {
		const req = getNodeRequire();
		const childProcess = req("node:child_process") as typeof import("node:child_process");
		const processRef = req("node:process") as typeof import("node:process");
		const path = req("node:path") as typeof import("node:path");

		// Extend PATH so Electron can find node/npx
		const homebrewBin = "/opt/homebrew/bin";
		const localBin = "/usr/local/bin";
		const currentPath = processRef.env["PATH"] ?? "";
		const extendedPath = [homebrewBin, localBin, currentPath].filter(Boolean).join(path.delimiter);

		const proc = childProcess.spawn(runtime.command, runtime.args, {
			stdio: "pipe",
			env: {
				...processRef.env,
				PATH: extendedPath,
				...runtime.env,
			},
		});

		const client = new StdioMcpClient(proc);
		client.attach();

		await client.request(
			"initialize",
			{
				protocolVersion: "2024-11-05",
				capabilities: {},
				clientInfo: { name: "substack-in-obsidian", version: "1.0.0" },
			},
			MCP_REQUEST_TIMEOUT_MS,
		);
		client.writeFrame({ jsonrpc: "2.0", method: "notifications/initialized" });
		return client;
	}

	async callTool(name: string, params: Record<string, unknown>, timeout = MCP_REQUEST_TIMEOUT_MS): Promise<unknown> {
		const resp = await this.request("tools/call", { name, arguments: params }, timeout);
		if (resp.error) throw new Error(`${name} failed: ${resp.error.message}`);
		// Playwright MCP returns { result: { content: [{ type: "text", text: "..." }] } }
		// The text field contains the JSON-serialised return value of the evaluated function.
		const content = (resp.result as Record<string, unknown> | undefined)?.content;
		if (Array.isArray(content)) {
			const first = content[0] as Record<string, unknown> | undefined;
			const text = first?.["text"];
			if (typeof text === "string") {
				try { return JSON.parse(text); } catch { return text; }
			}
		}
		return resp.result;
	}

	close(): void {
		if (!this.closed) {
			this.proc.kill();
			this.closed = true;
		}
	}

	private attach(): void {
		this.proc.stdout.on("data", (chunk: ChildStdoutChunk) => {
			const req = getNodeRequire();
			const bufferModule = req("node:buffer") as typeof import("node:buffer");
			this.buffer += typeof chunk === "string" ? chunk : bufferModule.Buffer.from(chunk).toString("utf8");
			let nl: number;
			while ((nl = this.buffer.indexOf("\n")) !== -1) {
				const line = this.buffer.slice(0, nl).trim();
				this.buffer = this.buffer.slice(nl + 1);
				if (!line) continue;
				try {
					const msg = JSON.parse(line) as JsonRpcResponse;
					if (msg.id !== undefined) {
						const pending = this.pending.get(msg.id);
						if (pending) {
							this.pending.delete(msg.id);
							pending.resolve(msg);
						}
					}
				} catch {
					// ignore non-JSON lines
				}
			}
		});

		this.proc.stderr.on("data", (chunk: ChildStdoutChunk) => {
			const req = getNodeRequire();
			const bufferModule = req("node:buffer") as typeof import("node:buffer");
			this.stderrChunks.push(typeof chunk === "string" ? chunk : bufferModule.Buffer.from(chunk).toString("utf8"));
		});

		this.proc.on("error", (err: Error) => {
			this.spawnError = err;
			this.closed = true;
			for (const [, p] of this.pending) p.reject(new Error(`MCP process closed. ${err.message}`));
			this.pending.clear();
		});

		this.proc.on("close", (code: number | null) => {
			if (!this.closed) {
				this.closed = true;
				const stderr = this.stderrChunks.join("").slice(-500);
				for (const [, p] of this.pending) {
					p.reject(new Error(`MCP process exited (code ${code ?? "?"}).\n${stderr}`));
				}
				this.pending.clear();
			}
		});

		this.proc.stdin.on("error", (err: Error) => {
			this.stdinError = err;
		});
	}

	private request(method: string, params: unknown, timeout: number): Promise<JsonRpcResponse> {
		if (this.closed || this.spawnError) {
			const msg = this.spawnError ? `MCP process closed. ${this.spawnError.message}` : "MCP client already closed";
			return Promise.reject(new Error(msg));
		}
		const id = this.nextId++;
		const frame: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };
		return new Promise<JsonRpcResponse>((resolve, reject) => {
			const timer = setTimeout(() => {
				this.pending.delete(id);
				reject(new Error(`tools/call timed out after ${timeout / 1000}s. Ensure the Playwright MCP Bridge extension is connected to a running Chrome/Edge window.`));
			}, timeout);
			this.pending.set(id, {
				resolve: (v) => { clearTimeout(timer); resolve(v); },
				reject: (e) => { clearTimeout(timer); reject(e); },
			});
			this.writeFrame(frame);
		});
	}

	private writeFrame(frame: unknown): void {
		if (this.closed || this.stdinError) return;
		try {
			this.proc.stdin.write(JSON.stringify(frame) + "\n");
		} catch {
			// ignore write errors after close
		}
	}
}

// ─── logging ──────────────────────────────────────────────────────────────────

function appendLog(plugin: SubstackPlugin, event: string, details: Record<string, unknown>): void {
	if (!plugin.settings.enableDebugLog) return;
	try {
		const req = getNodeRequire();
		const fs = req("node:fs") as typeof import("node:fs");
		const path = req("node:path") as typeof import("node:path");
		const adapter = plugin.app.vault.adapter;
		if (!(adapter instanceof FileSystemAdapter)) return;
		const logPath = path.join(
			adapter.getBasePath(),
			plugin.app.vault.configDir,
			"plugins",
			plugin.manifest.id,
			"logs",
			"publish.log",
		);
		fs.mkdirSync(path.dirname(logPath), { recursive: true });
		fs.appendFileSync(logPath, `[${new Date().toISOString()}] ${event}\n${JSON.stringify(details, null, 2)}\n\n`, "utf8");
	} catch {
		// logging must not break the flow
	}
}

// ─── util ─────────────────────────────────────────────────────────────────────

function getNodeRequire(): NodeRequireLike {
	const maybeRequire = (globalThis as RequireContainer).require;
	if (typeof maybeRequire === "function") return maybeRequire;
	throw new Error("Node require is not available in this environment.");
}
