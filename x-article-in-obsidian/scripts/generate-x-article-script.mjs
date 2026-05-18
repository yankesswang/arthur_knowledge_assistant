#!/usr/bin/env node
import { existsSync } from "node:fs";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

function printUsage() {
	console.log(`Usage:
  node scripts/generate-x-article-script.mjs <note.md> [options]

Options:
  --out=<file>                 Output file. Defaults to x-publish.generated.js
  --mode=browser|playwright-cli Output browser-console IIFE or playwright-cli snippet
  --title=<title>              Override frontmatter title
  --cover=<path-or-url>        Override frontmatter cover
  --vault=<dir>                Vault root for resolving Obsidian wikilink images
  --no-auto-apply-cover        Do not click X cover Apply automatically

Examples:
  node scripts/generate-x-article-script.mjs ./article.md
  node scripts/generate-x-article-script.mjs ./article.md --mode=playwright-cli --out=x.run.js
  playwright-cli open https://x.com --browser=chrome --headed --persistent
  playwright-cli run-code --filename=x.run.js`);
}

function parseArgs(argv) {
	const args = {
		input: "",
		out: "x-publish.generated.js",
		mode: "browser",
		title: null,
		cover: null,
		vault: null,
		autoApplyCover: true,
	};

	for (const arg of argv) {
		if (arg === "--help" || arg === "-h") {
			args.help = true;
			continue;
		}
		if (arg.startsWith("--out=")) {
			args.out = arg.slice("--out=".length);
			continue;
		}
		if (arg.startsWith("--mode=")) {
			args.mode = arg.slice("--mode=".length);
			continue;
		}
		if (arg.startsWith("--title=")) {
			args.title = arg.slice("--title=".length);
			continue;
		}
		if (arg.startsWith("--cover=")) {
			args.cover = arg.slice("--cover=".length);
			continue;
		}
		if (arg.startsWith("--vault=")) {
			args.vault = arg.slice("--vault=".length);
			continue;
		}
		if (arg === "--no-auto-apply-cover") {
			args.autoApplyCover = false;
			continue;
		}
		if (!args.input) {
			args.input = arg;
			continue;
		}
		throw new Error(`Unknown argument: ${arg}`);
	}

	if (args.mode !== "browser" && args.mode !== "playwright-cli") {
		throw new Error("--mode must be browser or playwright-cli");
	}

	return args;
}

function parseFrontmatter(source) {
	if (!source.startsWith("---\n")) {
		return { frontmatter: {}, body: source };
	}

	const end = source.indexOf("\n---", 4);
	if (end < 0) {
		return { frontmatter: {}, body: source };
	}

	const raw = source.slice(4, end);
	const body = source.slice(end + 4).replace(/^\r?\n/, "");
	const frontmatter = {};
	let currentObject = null;

	for (const line of raw.split(/\r?\n/)) {
		const objectMatch = line.match(/^([A-Za-z0-9_-]+):\s*$/);
		if (objectMatch?.[1]) {
			currentObject = objectMatch[1];
			frontmatter[currentObject] = {};
			continue;
		}

		const nestedMatch = line.match(/^\s+([A-Za-z0-9_-]+):\s*(.*)$/);
		if (nestedMatch?.[1] && currentObject && typeof frontmatter[currentObject] === "object") {
			frontmatter[currentObject][nestedMatch[1]] = unquoteYamlValue(nestedMatch[2] ?? "");
			continue;
		}

		const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
		if (match?.[1]) {
			currentObject = null;
			frontmatter[match[1]] = unquoteYamlValue(match[2] ?? "");
		}
	}

	return { frontmatter, body };
}

function unquoteYamlValue(value) {
	const trimmed = value.trim();
	if (
		(trimmed.startsWith('"') && trimmed.endsWith('"')) ||
		(trimmed.startsWith("'") && trimmed.endsWith("'"))
	) {
		return trimmed.slice(1, -1);
	}
	return trimmed;
}

function getFrontmatterString(frontmatter, keys) {
	const formatter = frontmatter.formatter;
	if (formatter && typeof formatter === "object") {
		for (const key of keys) {
			const value = formatter[key];
			if (typeof value === "string" && value.trim()) {
				return value.trim();
			}
		}
	}

	for (const key of keys) {
		const value = frontmatter[key];
		if (typeof value === "string" && value.trim()) {
			return value.trim();
		}
	}
	return null;
}

function normalizeImageTarget(target) {
	return target
		.trim()
		.replace(/^!\[\[|\]\]$/g, "")
		.replace(/^!\[[^\]]*\]\((.+)\)$/u, "$1")
		.replace(/^</, "")
		.replace(/>$/, "")
		.split("|")[0]
		.trim();
}

function extractPublishItems(markdown) {
	const segments = [];
	let match;

	const codePattern = /```([^\n`]*)\n([\s\S]*?)```/g;
	while ((match = codePattern.exec(markdown)) !== null) {
		segments.push({
			type: "code",
			start: match.index,
			end: match.index + match[0].length,
			language: (match[1] ?? "").trim(),
			code: (match[2] ?? "").replace(/\n$/, ""),
		});
	}

	const dividerPattern = /^(?: {0,3})(?:(?:-{3,})|(?:\*{3,})|(?:_{3,}))(?:[ \t]*)$/gm;
	while ((match = dividerPattern.exec(markdown)) !== null) {
		if (segments.some((segment) => match.index >= segment.start && match.index < segment.end)) continue;
		segments.push({ type: "divider", start: match.index, end: match.index + match[0].length });
	}

	const postUrlPattern =
		/^(?: {0,3})(https?:\/\/(?:www\.)?(?:x\.com|twitter\.com)\/[A-Za-z0-9_]+\/status\/\d+(?:\?[^\s]+)?)\s*$/gm;
	while ((match = postUrlPattern.exec(markdown)) !== null) {
		if (segments.some((segment) => match.index >= segment.start && match.index < segment.end)) continue;
		segments.push({ type: "post", start: match.index, end: match.index + match[0].length, url: match[1] });
	}

	const postMarkdownLinkPattern =
		/\[(https?:\/\/(?:www\.)?(?:x\.com|twitter\.com)\/[A-Za-z0-9_]+\/status\/\d+(?:\?[^\]\s]+)?)\]\((https?:\/\/(?:www\.)?(?:x\.com|twitter\.com)\/[A-Za-z0-9_]+\/status\/\d+(?:\?[^)\s]+)?)\)/g;
	while ((match = postMarkdownLinkPattern.exec(markdown)) !== null) {
		if (segments.some((segment) => match.index >= segment.start && match.index < segment.end)) continue;
		segments.push({ type: "post", start: match.index, end: match.index + match[0].length, url: match[2] ?? match[1] });
	}

	const imagePatterns = [
		{ kind: "markdown", pattern: /!\[([^\]]*)\]\(([^)]+)\)/g },
		{ kind: "wikilink", pattern: /!\[\[([^\]]+)\]\]/g },
	];
	for (const imagePattern of imagePatterns) {
		while ((match = imagePattern.pattern.exec(markdown)) !== null) {
			if (segments.some((segment) => match.index >= segment.start && match.index < segment.end)) continue;
			segments.push({
				type: "image",
				start: match.index,
				end: match.index + match[0].length,
				alt: imagePattern.kind === "markdown" ? (match[1] ?? "").trim() : "",
				target: imagePattern.kind === "markdown" ? match[2] ?? "" : match[1] ?? "",
			});
		}
	}

	segments.sort((left, right) => left.start - right.start);

	let processedMarkdown = markdown;
	for (let index = segments.length - 1; index >= 0; index -= 1) {
		const segment = segments[index];
		const marker = `MPH_MARKER_${index + 1}`;
		processedMarkdown =
			processedMarkdown.slice(0, segment.start) + `\n${marker}\n` + processedMarkdown.slice(segment.end);
	}

	return { processedMarkdown, segments };
}

async function buildPublishItems(segments, inputPath, vaultRoot) {
	const items = [];
	const inputDir = path.dirname(path.resolve(inputPath));

	for (let index = 0; index < segments.length; index += 1) {
		const segment = segments[index];
		const marker = `MPH_MARKER_${index + 1}`;
		if (segment.type === "code") {
			items.push({ type: "code", marker, language: segment.language, code: segment.code });
		} else if (segment.type === "divider") {
			items.push({ type: "divider", marker });
		} else if (segment.type === "post") {
			items.push({ type: "post", marker, url: segment.url });
		} else if (segment.type === "image") {
			const asset = await resolveImageAsset(segment.target, segment.alt, inputDir, vaultRoot);
			if (asset) items.push({ type: "image", marker, ...asset });
			else items.push({ type: "missing", marker });
		}
	}

	return items;
}

async function resolveImageAsset(rawTarget, alt, inputDir, vaultRoot) {
	const target = normalizeImageTarget(rawTarget);
	if (!target) return null;

	if (/^https?:\/\//i.test(target)) {
		const response = await fetch(target);
		if (!response.ok) return null;
		const arrayBuffer = await response.arrayBuffer();
		const mimeType = inferMimeType(target, response.headers.get("content-type") ?? "");
		return {
			alt,
			fileName: extractFileName(target, mimeType),
			mimeType,
			base64: Buffer.from(arrayBuffer).toString("base64"),
		};
	}

	const candidates = [
		path.resolve(inputDir, decodeURIComponent(target)),
		path.resolve(process.cwd(), decodeURIComponent(target)),
	];
	if (vaultRoot) {
		candidates.push(path.resolve(vaultRoot, decodeURIComponent(target)));
	}
	const filePath = candidates.find((candidate) => existsSync(candidate));
	const resolvedPath = filePath ?? (vaultRoot ? await findFileByBasename(vaultRoot, path.basename(target)) : null);
	if (!resolvedPath) return null;

	const data = await readFile(resolvedPath);
	return {
		alt,
		fileName: path.basename(resolvedPath),
		mimeType: inferMimeType(resolvedPath, ""),
		base64: data.toString("base64"),
	};
}

async function findFileByBasename(root, basename) {
	const queue = [root];
	const ignored = new Set([".git", ".obsidian", "node_modules"]);
	while (queue.length > 0) {
		const current = queue.shift();
		let entries;
		try {
			entries = await readdir(current, { withFileTypes: true });
		} catch {
			continue;
		}

		for (const entry of entries) {
			if (entry.isDirectory()) {
				if (!ignored.has(entry.name)) queue.push(path.join(current, entry.name));
				continue;
			}
			if (entry.isFile() && entry.name === basename) {
				return path.join(current, entry.name);
			}
		}
	}
	return null;
}

function findVaultRoot(inputPath) {
	let current = path.dirname(path.resolve(inputPath));
	while (true) {
		if (existsSync(path.join(current, ".obsidian"))) {
			return current;
		}
		const parent = path.dirname(current);
		if (parent === current) return null;
		current = parent;
	}
}

function inferMimeType(target, contentType) {
	const normalized = contentType.split(";")[0]?.trim().toLowerCase();
	if (normalized?.startsWith("image/")) return normalized;

	const extension = path.extname(target.split("?")[0] ?? "").toLowerCase();
	switch (extension) {
		case ".jpg":
		case ".jpeg":
			return "image/jpeg";
		case ".webp":
			return "image/webp";
		case ".gif":
			return "image/gif";
		case ".svg":
			return "image/svg+xml";
		default:
			return "image/png";
	}
}

function extractFileName(target, mimeType) {
	const cleanTarget = target.split("?")[0] ?? target;
	const last = cleanTarget.split("/").pop()?.trim();
	if (last) return last;
	const extension = mimeType.split("/")[1] ?? "png";
	return `remote-image.${extension}`;
}

function markdownToHtml(markdown) {
	const lines = markdown.replace(/\r\n/g, "\n").split("\n");
	const html = [];
	let paragraph = [];
	let list = [];

	const flushParagraph = () => {
		if (paragraph.length === 0) return;
		html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
		paragraph = [];
	};
	const flushList = () => {
		if (list.length === 0) return;
		html.push(`<ul>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
		list = [];
	};

	for (const line of lines) {
		const trimmed = line.trim();
		if (!trimmed) {
			flushParagraph();
			flushList();
			continue;
		}

		const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
		if (heading) {
			flushParagraph();
			flushList();
			html.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
			continue;
		}

		const blockquote = trimmed.match(/^>\s?(.+)$/);
		if (blockquote) {
			flushParagraph();
			flushList();
			html.push(`<blockquote>${inlineMarkdown(blockquote[1])}</blockquote>`);
			continue;
		}

		const unordered = trimmed.match(/^[-*+]\s+(.+)$/);
		if (unordered) {
			flushParagraph();
			list.push(unordered[1]);
			continue;
		}

		flushList();
		paragraph.push(trimmed);
	}

	flushParagraph();
	flushList();
	return html.join("\n");
}

function inlineMarkdown(value) {
	return escapeHtml(value)
		.replace(/`([^`]+)`/g, "<code>$1</code>")
		.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
		.replace(/\*([^*]+)\*/g, "<em>$1</em>")
		.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>');
}

function escapeHtml(value) {
	return value
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;");
}

function buildBrowserPublishFunction(payload) {
	return `async () => {
  const payload = ${JSON.stringify(payload, null, 2)};
  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  function findEditor() {
    return document.querySelector("[data-contents='true'] [contenteditable='true']") || document.querySelector("[contenteditable='true']");
  }

  function normalizeText(value) {
    return (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
  }

  function isVisibleElement(node) {
    if (!(node instanceof HTMLElement)) return false;
    const style = window.getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }

  function findClickableByText(labels) {
    const normalizedLabels = labels.map((label) => normalizeText(label));
    return Array.from(document.querySelectorAll("button, [role='button'], [role='menuitem'], [role='option']"))
      .filter((node) => isVisibleElement(node))
      .find((node) => {
        const text = normalizeText([node.textContent || "", node.getAttribute("aria-label") || "", node.getAttribute("data-testid") || ""].join(" "));
        return normalizedLabels.some((label) => text === label || text.includes(label));
      }) || null;
  }

  async function waitForSelector(selector, attempts = 30, delayMs = 200) {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const element = document.querySelector(selector);
      if (element) return element;
      await sleep(delayMs);
    }
    return null;
  }

  async function ensureArticleEditor() {
    let editor = findEditor();
    if (editor) return editor;

    const createButton =
      document.querySelector("button[aria-label='create']") ||
      Array.from(document.querySelectorAll("button[role='button'], button")).find((button) =>
        (button.getAttribute("aria-label") || "").toLowerCase() === "create"
      );
    if (createButton instanceof HTMLElement) {
      createButton.click();
      await sleep(1200);
    }

    editor = findEditor();
    if (!editor) throw new Error("X Article editor not found. Open https://x.com/compose/articles and create an article first.");
    return editor;
  }

  function findTitleField() {
    const editor = findEditor();
    const candidates = Array.from(document.querySelectorAll("input[type='text'], textarea, [contenteditable='true']"))
      .filter((node) => node !== editor && isVisibleElement(node));
    const titleKeywords = ["title", "标题", "add title", "输入标题"];
    candidates.sort((left, right) => {
      const score = (node) => {
        const text = normalizeText([node.getAttribute("aria-label") || "", node.getAttribute("placeholder") || "", node.getAttribute("data-testid") || ""].join(" "));
        const rect = node.getBoundingClientRect();
        return (titleKeywords.some((keyword) => text.includes(keyword)) ? 10 : 0) + (rect.top < 420 ? 4 : 0) + (rect.width > 240 ? 2 : 0);
      };
      return score(right) - score(left);
    });
    return candidates[0] || null;
  }

  async function setArticleTitle() {
    if (!payload.title) return;
    const titleField = findTitleField();
    if (!titleField) return;
    if (titleField instanceof HTMLInputElement || titleField instanceof HTMLTextAreaElement) {
      const proto = titleField instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(titleField, payload.title);
    } else {
      titleField.focus();
      document.execCommand("selectAll", false);
      document.execCommand("insertText", false, payload.title);
    }
    titleField.dispatchEvent(new Event("input", { bubbles: true }));
    titleField.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(250);
  }

  function pasteHtml(editor) {
    const data = new DataTransfer();
    data.setData("text/html", payload.html);
    data.setData("text/plain", payload.markdown);
    editor.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }

  async function insertArticleHtml() {
    const editor = await ensureArticleEditor();
    editor.focus();
    const before = (editor.textContent || "").replace(/\\s/g, "").length;
    pasteHtml(editor);
    await sleep(700);
    const after = (editor.textContent || "").replace(/\\s/g, "").length;
    if (after <= before) document.execCommand("insertHTML", false, payload.html);
    await sleep(700);
  }

  function findToken(token) {
    const editor = findEditor();
    if (!editor) return null;
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const offset = (node.textContent || "").indexOf(token);
      if (offset >= 0) return { node, offset };
    }
    return null;
  }

  function removeToken(token) {
    const found = findToken(token);
    if (!found) return false;
    const selection = window.getSelection();
    const range = document.createRange();
    range.setStart(found.node, found.offset);
    range.setEnd(found.node, found.offset + token.length);
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand("delete", false);
    selection.removeAllRanges();
    return true;
  }

  async function focusAfterToken(token) {
    const found = findToken(token);
    if (!found) return false;
    const selection = window.getSelection();
    const range = document.createRange();
    range.setStart(found.node, found.offset + token.length);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    findEditor()?.focus();
    await sleep(100);
    return true;
  }

  async function openInsertMenu(labels, token) {
    await focusAfterToken(token);
    const insertButton = findClickableByText(["插入", "insert"]);
    if (!insertButton) throw new Error("Insert button not found.");
    insertButton.click();
    await sleep(350);
    const option = findClickableByText(labels);
    if (!option) throw new Error("Insert option not found: " + labels.join("/"));
    option.click();
    await sleep(500);
  }

  function base64ToFile(base64, fileName, mimeType) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return new File([new Blob([bytes], { type: mimeType })], fileName, { type: mimeType });
  }

  async function setFileInput(input, asset) {
    const data = new DataTransfer();
    data.items.add(base64ToFile(asset.base64, asset.fileName, asset.mimeType));
    input.files = data.files;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(1200);
  }

  async function insertImage(item) {
    await openInsertMenu(["媒体", "media", "photo", "image"], item.marker);
    const input = await waitForSelector("input[type='file'], input[data-testid='fileInput']");
    if (!(input instanceof HTMLInputElement)) throw new Error("Media file input not found.");
    await setFileInput(input, item);
    removeToken(item.marker);
  }

  async function insertDivider(item) {
    await openInsertMenu(["分割线", "divider", "separator", "horizontal rule"], item.marker);
    await sleep(500);
    removeToken(item.marker);
  }

  async function insertCode(item) {
    await openInsertMenu(["代码", "code"], item.marker);
    const input = await waitForSelector("textarea[name='code-input'], [role='dialog'] textarea, textarea, [role='dialog'] [contenteditable='true']");
    if (!input) throw new Error("Code input not found.");
    if (input instanceof HTMLTextAreaElement) {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set?.call(input, item.code);
    } else {
      input.focus();
      document.execCommand("insertText", false, item.code);
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(200);
    const submit = findClickableByText(["插入", "insert"]);
    if (!(submit instanceof HTMLElement)) throw new Error("Code submit button not found.");
    submit.click();
    await sleep(800);
    removeToken(item.marker);
  }

  async function insertPost(item) {
    await openInsertMenu(["帖子", "posts", "post", "tweet"], item.marker);
    const input = await waitForSelector("input[name='TweetByUrlInput'], input[type='text'], input:not([type]), textarea");
    if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) throw new Error("Post URL input not found.");
    const proto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(input, item.url);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(500);
    const confirm = document.evaluate("//button/article", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue || findClickableByText(["插入", "insert", "确认", "confirm"]);
    if (!(confirm instanceof HTMLElement)) throw new Error("Post confirm button not found.");
    confirm.click();
    await sleep(1000);
    removeToken(item.marker);
  }

  async function uploadCover() {
    if (!payload.cover) return;
    const coverButton = findClickableByText(["封面", "cover", "add cover", "upload cover", "添加照片或视频", "add photos or video"]);
    if (!(coverButton instanceof HTMLElement)) return;
    coverButton.click();
    await sleep(500);
    const input = await waitForSelector("input[type='file'], input[data-testid='fileInput']");
    if (input instanceof HTMLInputElement) await setFileInput(input, payload.cover);
    if (payload.autoApplyCover !== false) {
      const applyButton = await waitForSelector("button[data-testid='applyButton']");
      if (applyButton instanceof HTMLElement) applyButton.click();
    }
  }

  await setArticleTitle();
  await insertArticleHtml();
  let processedItems = 0;
	for (const item of payload.items) {
    if (item.type === "image") await insertImage(item);
    else if (item.type === "divider") await insertDivider(item);
    else if (item.type === "code") await insertCode(item);
    else if (item.type === "post") await insertPost(item);
    else if (item.type === "missing") removeToken(item.marker);
    processedItems += 1;
    await sleep(500);
  }
  await uploadCover();
  return { ok: true, processedItems, totalItems: payload.items.length };
}`;
}

function buildOutput(payload, mode) {
	const browserFunction = buildBrowserPublishFunction(payload);
	if (mode === "playwright-cli") {
		return `// Run with: playwright-cli run-code --filename=this-file.js
async (page) => {
  await page.goto("https://x.com/compose/articles");
  await page.waitForTimeout(2000);
  const result = await page.evaluate(${browserFunction});
  console.log(JSON.stringify(result, null, 2));
}
`;
	}

	return `// Open https://x.com/compose/articles, create an article, then paste this into DevTools Console.
(${browserFunction})().then(console.log).catch(console.error);
`;
}

async function main() {
	const args = parseArgs(process.argv.slice(2));
	if (args.help || !args.input) {
		printUsage();
		process.exit(args.help ? 0 : 1);
	}

	const inputPath = path.resolve(args.input);
	const raw = await readFile(inputPath, "utf8");
	const { frontmatter, body } = parseFrontmatter(raw);
	const { processedMarkdown, segments } = extractPublishItems(body);
	const vaultRoot = args.vault ? path.resolve(args.vault) : findVaultRoot(inputPath);
	const items = await buildPublishItems(segments, inputPath, vaultRoot);
	const title = args.title ?? getFrontmatterString(frontmatter, ["title", "Title"]);
	const coverTarget = args.cover ?? getFrontmatterString(frontmatter, ["cover", "Cover"]);
	const cover = coverTarget ? await resolveImageAsset(coverTarget, "", path.dirname(inputPath), vaultRoot) : null;
	const payload = {
		html: markdownToHtml(processedMarkdown),
		markdown: processedMarkdown,
		items,
		title,
		cover,
		autoApplyCover: args.autoApplyCover,
	};
	const output = buildOutput(payload, args.mode);
	const outputPath = path.resolve(args.out);
	await mkdir(path.dirname(outputPath), { recursive: true });
	await writeFile(outputPath, output, "utf8");
	console.log(`Generated ${args.mode} script: ${outputPath}`);
	console.log(`Items: ${items.length}. Cover: ${cover ? "yes" : "no"}.`);
}

main().catch((error) => {
	console.error(error instanceof Error ? error.message : error);
	process.exit(1);
});
