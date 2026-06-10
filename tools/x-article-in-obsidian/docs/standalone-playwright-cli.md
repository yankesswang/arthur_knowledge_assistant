# Standalone X Article script

This workflow generates a copyable browser script from a Markdown file. It does
not require the Obsidian plugin runtime.

## Generate a browser-console script

```bash
npm run x:script -- ./article.md --out=x-publish.generated.js
```

Open `https://x.com/compose/articles`, create an article, then paste the
generated script into DevTools Console.

## Generate a Playwright CLI script

```bash
npm run x:script -- ./article.md --mode=playwright-cli --out=x.run.js
```

Open a persistent browser session:

```bash
npx playwright-cli open https://x.com --browser=chrome --headed --persistent
```

Log in to X manually if needed, then run:

```bash
npx playwright-cli run-code --filename=x.run.js
```

## Supported Markdown features

- Headings, paragraphs, links, bold, italic, inline code, blockquotes, and simple unordered lists.
- Fenced code blocks.
- Markdown images and Obsidian image wikilinks.
- X/Twitter status URLs on their own line.
- Horizontal dividers.
- Frontmatter `title`, `cover`, `formatter.title`, and `formatter.cover`.

The generated script uploads to the X Article editor as a draft. It does not
publish the article.
