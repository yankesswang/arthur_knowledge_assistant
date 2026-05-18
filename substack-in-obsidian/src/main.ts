import { Plugin, WorkspaceLeaf } from "obsidian";
import { SubstackSettingTab, SubstackPluginSettings, DEFAULT_SETTINGS } from "./settings";
import { SUBSTACK_PREVIEW_VIEW_TYPE, COMMANDS } from "./constants";
import { SubstackPreviewView } from "./views/SubstackPreviewView";
import { uploadToSubstackDraft } from "./commands/publishToSubstack";

export default class SubstackPlugin extends Plugin {
	settings!: SubstackPluginSettings;

	async onload(): Promise<void> {
		await this.loadSettings();

		this.registerView(SUBSTACK_PREVIEW_VIEW_TYPE, (leaf) => new SubstackPreviewView(leaf, this));

		// Ribbon icon
		this.addRibbonIcon("file-text", "Open Substack preview", () => this.openPreview());

		// Commands
		this.addCommand({
			id: COMMANDS.OPEN_PREVIEW,
			name: "Open preview",
			callback: () => this.openPreview(),
		});

		this.addCommand({
			id: COMMANDS.UPLOAD_DRAFT,
			name: "Upload draft to Substack",
			callback: () => uploadToSubstackDraft(this),
		});

		this.addSettingTab(new SubstackSettingTab(this.app, this));
	}

	async onunload(): Promise<void> {
		this.app.workspace.detachLeavesOfType(SUBSTACK_PREVIEW_VIEW_TYPE);
	}

	async loadSettings(): Promise<void> {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings(): Promise<void> {
		await this.saveData(this.settings);
	}

	private async openPreview(): Promise<void> {
		const existing = this.app.workspace.getLeavesOfType(SUBSTACK_PREVIEW_VIEW_TYPE);
		if (existing.length > 0) {
			this.app.workspace.revealLeaf(existing[0] as WorkspaceLeaf);
			return;
		}
		const leaf = this.app.workspace.getRightLeaf(false);
		if (!leaf) return;
		await leaf.setViewState({ type: SUBSTACK_PREVIEW_VIEW_TYPE, active: true });
		this.app.workspace.revealLeaf(leaf);
	}
}
