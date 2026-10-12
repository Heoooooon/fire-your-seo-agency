import assert from "node:assert/strict";
import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(process.argv[2] ?? join(dirname(fileURLToPath(import.meta.url)), ".."));
const senpi = process.env.SENPI_ROOT ?? join(homedir(), ".bun/install/global/node_modules/@code-yeongyu/senpi");
const { DefaultResourceLoader } = await import(`${senpi}/dist/core/resource-loader.js`);
const { SettingsManager } = await import(`${senpi}/dist/core/settings-manager.js`);

// 설치 설정을 쓰지 않고 예제 패키지와 같은 실제 로더를 사용한다.
const loader = new DefaultResourceLoader({
  cwd: root,
  agentDir: join(root, ".absent-agent"),
  settingsManager: SettingsManager.inMemory(),
  noContextFiles: true,
  additionalExtensionPaths: [root],
});
await loader.reload();
const { skills, diagnostics } = loader.getSkills();
assert.deepEqual(diagnostics.filter((item) => String(item.path ?? "").startsWith(root)), []);
const skill = skills.find((item) => item.name === "fire-your-seo-agency");
assert.ok(skill, "fire-your-seo-agency was not discovered from package.json");
assert.equal(realpathSync(skill.filePath), realpathSync(join(root, "skills/fire-your-seo-agency/SKILL.md")));
assert.ok(skill.description.length > 0 && skill.description.length <= 1024);
console.log(`PASS Senpi package discovery: ${skill.name}`);
console.log(`PASS Frontmatter: ${skill.description.length} description characters, no package diagnostics`);
