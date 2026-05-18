import { App, PluginSettingTab, Setting } from "obsidian";
import type SubstackPlugin from "./main";

export interface SubstackPluginSettings {
	substackUrl: string;
	playwrightToken: string;
	enableDebugLog: boolean;
	autoRefresh: boolean;
	stripFrontmatter: boolean;
	useFilenameAsTitle: boolean;
}

export const DEFAULT_SETTINGS: SubstackPluginSettings = {
	substackUrl: "",
	playwrightToken: "",
	enableDebugLog: false,
	autoRefresh: true,
	stripFrontmatter: true,
	useFilenameAsTitle: true,
};

export class SubstackSettingTab extends PluginSettingTab {
	constructor(app: App, private plugin: SubstackPlugin) {
		super(app, plugin);
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		new Setting(containerEl).setName("Substack publication URL").setDesc(
			'Your Substack URL, e.g. https://yourname.substack.com'
		).addText((text) =>
			text
				.setPlaceholder("https://yourname.substack.com")
				.setValue(this.plugin.settings.substackUrl)
				.onChange(async (value) => {
					this.plugin.settings.substackUrl = value.trim().replace(/\/$/, "");
					await this.plugin.saveSettings();
				})
		);

		new Setting(containerEl).setName("Playwright MCP token").setDesc(
			"PLAYWRIGHT_MCP_EXTENSION_TOKEN from the Playwright MCP Bridge Chrome extension. Paste only the token value (after the = sign)."
		).addText((text) =>
			text
				.setPlaceholder("Mau_xxxxxxxx")
				.setValue(this.plugin.settings.playwrightToken)
				.onChange(async (value) => {
					// Strip key= prefix if user accidentally pastes the full env var
					const cleaned = value.trim().replace(/^PLAYWRIGHT_MCP_EXTENSION_TOKEN=/i, "");
					this.plugin.settings.playwrightToken = cleaned;
					await this.plugin.saveSettings();
				})
		);

		new Setting(containerEl).setHeading().setName("Preview");

		new Setting(containerEl).setName("Auto refresh").setDesc(
			"Automatically refresh the preview when editing."
		).addToggle((toggle) =>
			toggle.setValue(this.plugin.settings.autoRefresh).onChange(async (value) => {
				this.plugin.settings.autoRefresh = value;
				await this.plugin.saveSettings();
			})
		);

		new Setting(containerEl).setName("Hide frontmatter").setDesc(
			"Hide YAML frontmatter in the preview pane."
		).addToggle((toggle) =>
			toggle.setValue(this.plugin.settings.stripFrontmatter).onChange(async (value) => {
				this.plugin.settings.stripFrontmatter = value;
				await this.plugin.saveSettings();
			})
		);

		new Setting(containerEl).setName("Use filename as title").setDesc(
			"When no # heading is found, use the file name as the post title."
		).addToggle((toggle) =>
			toggle.setValue(this.plugin.settings.useFilenameAsTitle).onChange(async (value) => {
				this.plugin.settings.useFilenameAsTitle = value;
				await this.plugin.saveSettings();
			})
		);

		new Setting(containerEl).setHeading().setName("Debug");

		new Setting(containerEl).setName("Enable debug log").setDesc(
			"Write publish events to logs/publish.log inside the plugin folder."
		).addToggle((toggle) =>
			toggle.setValue(this.plugin.settings.enableDebugLog).onChange(async (value) => {
				this.plugin.settings.enableDebugLog = value;
				await this.plugin.saveSettings();
			})
		);
	}
}
