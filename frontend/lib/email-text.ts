const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

function decodeEntities(text: string) {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, code: string) => {
    if (code[0] !== "#") return ENTITIES[code.toLowerCase()] ?? match;
    const hex = code[1] === "x" || code[1] === "X";
    return String.fromCodePoint(parseInt(code.slice(hex ? 2 : 1), hex ? 16 : 10));
  });
}

function escapeHtml(text: string) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function htmlToText(html: string) {
  const text = html
    .replace(/<(script|style)\b[\s\S]*?<\/\1\s*>/gi, "")
    .replace(/<a\b[^>]*?\bhref\s*=\s*["']([^"']*)["'][^>]*>([\s\S]*?)<\/a\s*>/gi, (_, href: string, label: string) => {
      const shown = label.replace(/<[^>]+>/g, "").trim();
      return !shown || decodeEntities(shown) === decodeEntities(href) ? href : `[${shown}](${href})`;
    })
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<li\b[^>]*>/gi, "\n- ")
    .replace(/<\/(p|div|ul|ol|table|tr|h[1-6]|blockquote)\s*>/gi, "\n\n")
    .replace(/<[^>]+>/g, "");
  return decodeEntities(text)
    .split("\n")
    .map((line) => line.replace(/[ \t ]+/g, " ").trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const LINK = /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<]+[^\s<.,;:!?)\]])/g;

function linkify(line: string) {
  return line.replace(LINK, (_, label: string | undefined, href: string | undefined, bare: string | undefined) =>
    label && href ? `<a href="${href}">${label}</a>` : `<a href="${bare}">${bare}</a>`,
  );
}

export function textToHtml(text: string) {
  return text
    .trim()
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph) => `<p>${paragraph.split("\n").map((line) => linkify(escapeHtml(line.trim()))).join("<br>")}</p>`)
    .join("");
}
