import {
	ItemView,
	MarkdownRenderer,
	MarkdownView,
	TFile,
	WorkspaceLeaf,
	Notice,
} from "obsidian";
import { SUBSTACK_PREVIEW_VIEW_TYPE } from "../constants";
import type SubstackPlugin from "../main";
import { uploadToSubstackDraft } from "../commands/publishToSubstack";

const FRONTMATTER_RE = /^---\n[\s\S]*?\n---\n*/;

export class SubstackPreviewView extends ItemView {
	private toolbarEl!: HTMLDivElement;
	private heroCoverEl!: HTMLDivElement;
	private heroTitleEl!: HTMLDivElement;
	private heroSummaryEl!: HTMLDivElement;
	private noticeEl!: HTMLDivElement;
	private articleEl!: HTMLDivElement;
	private uploadBtnEl!: HTMLButtonElement;
	private refreshBtnEl!: HTMLButtonElement;

	private isUploading = false;
	private refreshToken = 0;
	private refreshTimer: number | null = null;

	private lastTargetFilePath: string | null = null;
	private sourceScrollEl: HTMLElement | null = null;
	private sourceScrollHandler: (() => void) | null = null;

	constructor(leaf: WorkspaceLeaf, private plugin: SubstackPlugin) {
		super(leaf);
	}

	getViewType(): string { return SUBSTACK_PREVIEW_VIEW_TYPE; }
	getDisplayText(): string { return "Substack preview"; }
	getIcon(): string { return "newspaper"; }

	async onOpen(): Promise<void> {
		this.contentEl.empty();
		this.contentEl.addClass("substack-preview-view");

		// ── shell layout ─────────────────────────────────────────────────────
		const shell = this.contentEl.createDiv({ cls: "substack-shell" });
		this.toolbarEl = shell.createDiv({ cls: "substack-toolbar" });

		this.uploadBtnEl = this.toolbarEl.createEl("button", {
			cls: "substack-btn-primary",
			text: "Upload draft",
		});
		this.uploadBtnEl.addEventListener("click", () => void this.upload());

		this.refreshBtnEl = this.toolbarEl.createEl("button", {
			cls: "substack-btn",
			text: "Refresh",
		});
		this.refreshBtnEl.addEventListener("click", () => void this.refresh());

		// ── hero card (title + cover + summary) ──────────────────────────────
		const hero = shell.createDiv({ cls: "substack-hero" });
		this.heroCoverEl = hero.createDiv({ cls: "substack-hero__cover" });
		const heroBody = hero.createDiv({ cls: "substack-hero__body" });
		heroBody.createDiv({ cls: "substack-hero__badge" }).setText("Preview");
		this.heroTitleEl = heroBody.createDiv({ cls: "substack-hero__title" });
		this.heroSummaryEl = heroBody.createDiv({ cls: "substack-hero__summary" });

		// ── article body ─────────────────────────────────────────────────────
		const card = shell.createDiv({ cls: "substack-card" });
		this.noticeEl = card.createDiv({ cls: "substack-draft-notice" });
		this.noticeEl.setText("Draft preview — not published");
		this.articleEl = card.createDiv({ cls: "substack-body markdown-rendered" });

		// ── events ───────────────────────────────────────────────────────────
		this.registerEvent(
			this.app.workspace.on("file-open", (file) => {
				if (file instanceof TFile && file.extension === "md") {
					this.lastTargetFilePath = file.path;
				}
				this.queueRefresh();
			}),
		);
		this.registerEvent(
			this.app.workspace.on("active-leaf-change", () => {
				this.captureTargetMarkdownView();
				this.bindScrollSync();
				this.queueRefresh();
			}),
		);
		this.registerEvent(
			this.app.workspace.on("editor-change", () => this.queueRefresh()),
		);
		this.registerEvent(
			this.app.vault.on("modify", (file) => {
				const active = this.getTargetMarkdownView();
				if (active?.file && file.path === active.file.path) this.queueRefresh();
			}),
		);

		this.captureTargetMarkdownView();
		this.bindScrollSync();
		await this.refresh();
	}

	async onClose(): Promise<void> {
		if (this.refreshTimer !== null) {
			window.clearTimeout(this.refreshTimer);
			this.refreshTimer = null;
		}
		this.unbindScrollSync();
		this.contentEl.empty();
	}

	// ── debounced refresh ─────────────────────────────────────────────────────

	queueRefresh(): void {
		if (!this.plugin.settings.autoRefresh) return;
		if (this.refreshTimer !== null) window.clearTimeout(this.refreshTimer);
		this.refreshTimer = window.setTimeout(() => {
			this.refreshTimer = null;
			void this.refresh();
		}, 120);
	}

	async refresh(): Promise<void> {
		const token = ++this.refreshToken;
		this.refreshBtnEl.disabled = true;

		const context = this.getTargetContext();
		if (!context) {
			this.renderEmpty();
			this.refreshBtnEl.disabled = false;
			return;
		}

		try {
			const { md, title, subtitle } = this.parseContent(context.file, context.content);

			this.articleEl.empty();
			await MarkdownRenderer.render(this.app, md, this.articleEl, context.file.path, this);
			if (token !== this.refreshToken) return;

			this.renderHero(context.file, title, subtitle);
			this.syncToSourceScroll();
		} catch (e) {
			console.error("Substack preview render error", e);
			new Notice("Substack preview: render failed");
		} finally {
			this.refreshBtnEl.disabled = false;
		}
	}

	// ── upload ────────────────────────────────────────────────────────────────

	private async upload(): Promise<void> {
		if (this.isUploading) return;
		this.isUploading = true;
		this.uploadBtnEl.disabled = true;
		this.uploadBtnEl.setText("Uploading…");
		try {
			await uploadToSubstackDraft(this.plugin);
		} finally {
			this.isUploading = false;
			this.uploadBtnEl.disabled = false;
			this.uploadBtnEl.setText("Upload draft");
		}
	}

	// ── content parsing ───────────────────────────────────────────────────────

	private parseContent(file: TFile, raw: string): { md: string; title: string; subtitle: string } {
		let md = this.plugin.settings.stripFrontmatter ? raw.replace(FRONTMATTER_RE, "").trimStart() : raw;

		// Extract subtitle from frontmatter
		let subtitle = "";
		const fmMatch = raw.match(/^---\n([\s\S]*?)\n---/);
		if (fmMatch) {
			const fm = fmMatch[1] ?? "";
			const m = fm.match(/^(?:subtitle|description):\s*(.+)$/im);
			if (m?.[1]) subtitle = m[1].trim().replace(/^["']|["']$/g, "");
		}

		// Extract title from first h1 heading
		let title = "";
		const headingMatch = md.match(/^#\s+(.+)$/m);
		if (headingMatch?.[1]) {
			title = headingMatch[1].trim();
			md = md.replace(/^#\s+.+\n?/m, "").trimStart();
		} else if (this.plugin.settings.useFilenameAsTitle) {
			title = file.basename;
		}

		return { md, title, subtitle };
	}

	// ── hero card ─────────────────────────────────────────────────────────────

	private renderHero(file: TFile, title: string, subtitle: string): void {
		this.heroTitleEl.setText(title || file.basename);

		// Summary: first paragraph text from rendered article
		const firstPara = this.articleEl.querySelector("p");
		const summary = subtitle || firstPara?.textContent?.trim().slice(0, 200) || "";
		this.heroSummaryEl.setText(summary);

		// Cover image
		const coverSrc = this.resolveCoverSrc(file);
		if (coverSrc) {
			this.heroCoverEl.addClass("has-image");
			this.heroCoverEl.style.setProperty("--substack-cover", `url("${coverSrc}")`);
		} else {
			this.heroCoverEl.removeClass("has-image");
			this.heroCoverEl.style.removeProperty("--substack-cover");
		}
	}

	private resolveCoverSrc(file: TFile): string | null {
		const fm = this.app.metadataCache.getFileCache(file)?.frontmatter as Record<string, unknown> | undefined;
		const formatter = fm?.["formatter"];
		const raw = ((fm?.["cover"] ?? (formatter && typeof formatter === "object" && !Array.isArray(formatter) ? (formatter as Record<string, unknown>)["cover"] : undefined) ?? "") as string);
		if (!raw) return null;
		const name = raw.replace(/^!\[\[|\]\]$/g, "").replace(/^!\[[^\]]*\]\((.+)\)$/, "$1").trim();
		if (/^https?:\/\//i.test(name)) return name;
		const linked = this.app.metadataCache.getFirstLinkpathDest(name, file.path);
		if (linked instanceof TFile) return this.app.vault.getResourcePath(linked);
		return null;
	}

	private renderEmpty(): void {
		this.heroTitleEl.setText("No note open");
		this.heroSummaryEl.setText("Open a Markdown note to see the preview.");
		this.heroCoverEl.removeClass("has-image");
		this.heroCoverEl.style.removeProperty("--substack-cover");
		this.articleEl.empty();
		this.articleEl.createDiv({ cls: "substack-empty" }).setText("Open a Markdown note to preview it here.");
	}

	// ── scroll sync ───────────────────────────────────────────────────────────

	private bindScrollSync(): void {
		const next = this.getSourceScrollElement();
		if (next === this.sourceScrollEl) return;
		this.unbindScrollSync();
		if (!next) return;
		const handler = () => this.syncToSourceScroll();
		next.addEventListener("scroll", handler, { passive: true });
		this.sourceScrollEl = next;
		this.sourceScrollHandler = handler;
		this.syncToSourceScroll();
	}

	private unbindScrollSync(): void {
		if (this.sourceScrollEl && this.sourceScrollHandler) {
			this.sourceScrollEl.removeEventListener("scroll", this.sourceScrollHandler);
		}
		this.sourceScrollEl = null;
		this.sourceScrollHandler = null;
	}

	private getSourceScrollElement(): HTMLElement | null {
		const view = this.getTargetMarkdownView();
		if (!view) return null;
		return view.containerEl.querySelector(".cm-scroller") ?? view.containerEl.querySelector(".markdown-preview-view");
	}

	private syncToSourceScroll(): void {
		if (!this.sourceScrollEl) return;
		const srcScrollable = this.sourceScrollEl.scrollHeight - this.sourceScrollEl.clientHeight;
		const previewScrollable = this.contentEl.scrollHeight - this.contentEl.clientHeight;
		if (srcScrollable <= 0 || previewScrollable <= 0) return;
		const ratio = this.sourceScrollEl.scrollTop / srcScrollable;
		this.contentEl.scrollTop = previewScrollable * ratio;
	}

	// ── target view tracking ─────────────────────────────────────────────────

	private captureTargetMarkdownView(): void {
		const activeFile = this.app.workspace.activeEditor?.file;
		if (activeFile) { this.lastTargetFilePath = activeFile.path; return; }
		const active = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (active?.file && active.leaf !== this.leaf) this.lastTargetFilePath = active.file.path;
	}

	private getTargetContext(): { file: TFile; content: string } | null {
		const view = this.getTargetMarkdownView();
		if (view?.file) {
			this.lastTargetFilePath = view.file.path;
			return { file: view.file, content: view.editor.getValue() };
		}
		return null;
	}

	private getTargetMarkdownView(): MarkdownView | null {
		// Try last known file path first
		if (this.lastTargetFilePath) {
			const leaf = this.app.workspace.getLeavesOfType("markdown").find(
				(l) => l !== this.leaf && l.view instanceof MarkdownView && l.view.file?.path === this.lastTargetFilePath,
			);
			if (leaf?.view instanceof MarkdownView) return leaf.view;
		}
		// Then try active editor
		const activeFile = this.app.workspace.activeEditor?.file;
		if (activeFile) {
			const leaf = this.app.workspace.getLeavesOfType("markdown").find(
				(l) => l !== this.leaf && l.view instanceof MarkdownView && l.view.file?.path === activeFile.path,
			);
			if (leaf?.view instanceof MarkdownView) return leaf.view;
		}
		// Fallback: any markdown view that isn't this one
		const active = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (active && active.leaf !== this.leaf) return active;
		const fallback = this.app.workspace.getLeavesOfType("markdown").find(
			(l) => l !== this.leaf && l.view instanceof MarkdownView && Boolean((l.view as MarkdownView).file),
		);
		return fallback?.view instanceof MarkdownView ? fallback.view : null;
	}
}
