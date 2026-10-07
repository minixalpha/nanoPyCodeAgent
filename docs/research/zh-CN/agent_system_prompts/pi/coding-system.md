# Pi：编码代理分段提示词

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/pi/coding-system.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`b7dfc049e917a265a5aefa9f3952a2dec9b81cfd`
- [原始来源](https://github.com/earendil-works/pi/blob/b7dfc049e917a265a5aefa9f3952a2dec9b81cfd/packages/coding-agent/src/core/system-prompt.ts)
- 定位：`whole file`
- 来源文件: [packages/coding-agent/src/core/system-prompt.ts](../../../../../references/pi/packages/coding-agent/src/core/system-prompt.ts)
- 来源文件 SHA256: `e9cf234637f792c44e71764b8daff13bc15b0e77aa5574ec9728365ac9f61807`
- 中文译文 SHA256: `d456a0bb82161b39f959772a7b6021b5ca0c8d9e3c3ea6dc3c0bfc3e9bb653af`
- 英文原文 SHA256: `e9cf234637f792c44e71764b8daff13bc15b0e77aa5574ec9728365ac9f61807`
- [上游许可证](../../../agent_system_prompts/licenses/pi.txt)

完整组装器源码；含运行时变量，不冒充某次请求的最终文本。

buildSystemPromptSections/buildSystemPromptState 组装 preamble、tools、rules、docs、项目上下文、技能和 cwd；forceSystemPrompt 可整体替换。

## 内容方向

- 基础身份很短；工具摘要只列出实际提供 snippet 的工具，规则来自已选择工具并去重。
- Pi 自身文档按问题加载；项目规则和技能单独分段；不同段落可以独立更新。
- 基础规则主要是工具发现、简洁与路径表达；不能把工具贡献的指导或扩展 hook 当成基础身份中的内容。

## 对 nanoPyCodeAgent 的启示

借鉴保持核心短小、行为指导与工具能力一致。缺失的验收与验证规则可以小幅增加，但需要实验，不能以其他项目提示词长度决定效果。

## 中文译文

本节翻译生成器源码中的自然语言注释和提示词字符串，保留代码结构；它是供阅读的源码译本，不是实际请求的运行捕获。

````text
/**
 * 系统提示词构造与项目上下文加载
 */

import { getSystemMessageText } from "@earendil-works/pi-ai";
import { getDocsPath, getExamplesPath, getReadmePath } from "../config.ts";
import { formatSkillsForPrompt, type Skill } from "./skills.ts";

export interface BuildSystemPromptOptions {
	/** 自定义系统提示词，替换默认前缀。 */
	customPrompt?: string;
	/** 由 before_agent_start 处理器指定的完整提示词精确替换值。 */
	forceSystemPrompt?: string;
	/** 提示词包含的工具，默认 [read, bash, edit, write]。 */
	selectedTools?: string[];
	/** 按工具名索引的可选单行工具说明。 */
	toolSnippets?: Record<string, string>;
	/** 各工具提供的指导列表，按工具名索引。 */
	toolGuidelines?: Record<string, string[]>;
	/** 追加到默认系统提示词规则中的额外指导项。 */
	promptGuidelines?: string[];
	/** 来自用户配置的追加文本，位于项目上下文、技能和 cwd 之前。 */
	appendSystemPrompt?: string;
	/** 额外的 XML 包裹提示词区段，按标签名索引。 */
	sections?: Record<string, string>;
	/** 工作目录。 */
	cwd: string;
	/** 预加载的上下文文件。 */
	contextFiles?: Array<{ path: string; content: string }>;
	/** 预加载的技能。 */
	skills?: Skill[];
}

export type NormalizedBuildSystemPromptOptions = BuildSystemPromptOptions & {
	selectedTools: string[];
	toolSnippets: Record<string, string>;
	toolGuidelines: Record<string, string[]>;
	promptGuidelines: string[];
	appendSystemPrompt: string;
	sections: Record<string, string>;
	contextFiles: Array<{ path: string; content: string }>;
	skills: Skill[];
};

/**
 * 有序系统提示词区段，按名称索引。`preamble` 是无标签文本；其他区段
 * 均包裹在同名标签中，使模型能够对应后续更新。
 * 它们成为会话记录中的 `SystemMessage.sections`。
 */
export type SystemPromptSections = Record<string, string>;

const SYSTEM_PROMPT_SECTION_NAME = /^[a-z][a-z0-9_-]*$/;
/** 将提示词输入规范化为向扩展开放的可变形式，并补齐所有集合。 */
export function normalizeBuildSystemPromptOptions(input: BuildSystemPromptOptions): NormalizedBuildSystemPromptOptions {
	return {
		customPrompt: input.customPrompt,
		forceSystemPrompt: input.forceSystemPrompt,
		selectedTools: [...(input.selectedTools ?? ["read", "bash", "edit", "write"])],
		toolSnippets: { ...(input.toolSnippets ?? {}) },
		toolGuidelines: Object.fromEntries(
			Object.entries(input.toolGuidelines ?? {}).map(([name, guidelines]) => [name, [...guidelines]]),
		),
		promptGuidelines: [...(input.promptGuidelines ?? [])],
		appendSystemPrompt: input.appendSystemPrompt ?? "",
		sections: { ...(input.sections ?? {}) },
		cwd: input.cwd,
		contextFiles: (input.contextFiles ?? []).map((file) => ({ ...file })),
		skills: (input.skills ?? []).map((skill) => ({ ...skill })),
	};
}

function renderProjectContext(contextFiles: Array<{ path: string; content: string }>): string {
	return [
		"项目专用指令与指导：",
		...contextFiles.map(
			({ path, content }) => `<project_instructions path="${path}">\n${content}\n</project_instructions>`,
		),
	].join("\n\n");
}

function buildRules(
	selectedTools: string[],
	toolGuidelines: Record<string, string[]>,
	promptGuidelines: string[],
): string {
	const rules: string[] = [];
	const seen = new Set<string>();
	const addRule = (rule: string): void => {
		const normalized = rule.trim();
		if (!normalized || seen.has(normalized)) return;
		seen.add(normalized);
		rules.push(normalized);
	};

	const hasBash = selectedTools.includes("bash");
	const hasPowerShell = selectedTools.includes("powershell");
	const hasGrep = selectedTools.includes("grep");
	const hasFind = selectedTools.includes("find");
	const hasLs = selectedTools.includes("ls");

	if ((hasBash || hasPowerShell) && !hasGrep && !hasFind && !hasLs) {
		if (hasBash && hasPowerShell) {
			addRule("使用 bash 或 PowerShell 列出、搜索和查找文件等文件操作");
		} else if (hasPowerShell) {
			addRule("使用 PowerShell 列出、搜索和查找文件等文件操作");
		} else {
			addRule("使用 bash 执行 ls、rg、find 等文件操作");
		}
	}

	for (const name of selectedTools) {
		for (const rule of toolGuidelines[name] ?? []) addRule(rule);
	}
	for (const rule of promptGuidelines) addRule(rule);
	addRule("回复保持简洁");
	addRule("处理文件时清楚显示文件路径");
	return rules.map((rule) => `- ${rule}`).join("\n");
}

/** 构建结构化系统提示词的有序、可独立替换区段。 */
export function buildSystemPromptSections(input: BuildSystemPromptOptions): SystemPromptSections {
	const options = normalizeBuildSystemPromptOptions(input);
	const {
		customPrompt,
		selectedTools,
		toolSnippets,
		toolGuidelines,
		promptGuidelines,
		appendSystemPrompt,
		sections: customSections,
		cwd,
		contextFiles,
		skills,
	} = options;

	for (const name of Object.keys(customSections)) {
		if (!SYSTEM_PROMPT_SECTION_NAME.test(name) || name === "preamble") {
			throw new Error(`无效的系统提示词区段名称： ${name}`);
		}
	}

	const promptSections: Record<string, string> = {};
	if (customPrompt) {
		promptSections.preamble = customPrompt;
	} else {
		promptSections.preamble =
			"你是在编码代理宿主 pi 中工作的专业编码助手。通过读取文件、执行命令、编辑代码和创建文件帮助用户。";
		const visibleTools = selectedTools.filter((name) => !!toolSnippets[name]);
		const tools =
			visibleTools.length > 0 ? visibleTools.map((name) => `- ${name}: ${toolSnippets[name]}`).join("\n") : "（无）";
		promptSections.tools = `${tools}\n\n除上述工具外，根据项目情况，你还可能获得其他自定义工具。`;
		promptSections.rules = buildRules(selectedTools, toolGuidelines, promptGuidelines);
		promptSections.docs = `Pi 文档（仅当用户询问 pi 本身、SDK、扩展、主题、技能或 TUI 时读取）：
- 主要文档： ${getReadmePath()}
- 补充文档： ${getDocsPath()}
- 示例： ${getExamplesPath()} （扩展、自定义工具、SDK）
- 读取 pi 文档或示例时，docs/... 相对“补充文档”解析，examples/... 相对“示例”解析，不相对当前工作目录
- 询问以下内容时：扩展（docs/extensions.md、examples/extensions/）、主题（docs/themes.md）、技能（docs/skills.md）、提示词模板（docs/prompt-templates.md）、TUI 组件（docs/tui.md）、快捷键（docs/keybindings.md）、SDK 集成（docs/sdk.md）、自定义提供方（docs/custom-provider.md）、添加模型（docs/models.md）、pi 包（docs/packages.md）、环境变量（docs/environment-variables.md）、MCP 服务器（docs/mcp.md）、codemode 脚本及分类器、图像模型等非 LLM 模型（docs/codemode.md）
- 处理 pi 相关主题时，实现前阅读文档和示例，并跟进 .md 交叉引用
- 始终完整读取 pi 的 .md 文件，并跟进相关文档链接，例如 tui.md 中的 TUI API 细节`;
	}

	if (appendSystemPrompt) promptSections.addendum = appendSystemPrompt;
	if (contextFiles.length > 0) promptSections.project_context = renderProjectContext(contextFiles);
	const skillFileReadTool = (["read", "bash"] as const).find((tool) => selectedTools.includes(tool));
	if (skillFileReadTool && skills.length > 0) {
		const skillsPrompt = formatSkillsForPrompt(skills, skillFileReadTool).trim();
		if (skillsPrompt) promptSections.skills = skillsPrompt;
	}
	promptSections.cwd = cwd.replace(/\\/g, "/");
	for (const [name, content] of Object.entries(customSections)) {
		if (content) promptSections[name] = content;
	}

	const sections: SystemPromptSections = { preamble: promptSections.preamble };
	for (const [name, content] of Object.entries(promptSections)) {
		if (name !== "preamble") sections[name] = `<${name}>\n${content}\n</${name}>`;
	}
	return sections;
}

/**
 * `input` 的完整提示词状态。强制提示词作为不透明文本存于 `content`，
 * 不含区段；否则 `content` 为空，由结构化区段承载提示词。
 */
export function buildSystemPromptState(input: BuildSystemPromptOptions): {
	content: string;
	sections?: SystemPromptSections;
} {
	if (input.forceSystemPrompt !== undefined) return { content: input.forceSystemPrompt };
	return { content: "", sections: buildSystemPromptSections(input) };
}

/** 构建系统提示词文本，渲染形式与会话记录中系统消息的重放结果完全一致。 */
export function buildSystemPrompt(input: BuildSystemPromptOptions): string {
	return getSystemMessageText({ role: "system", ...buildSystemPromptState(input), timestamp: 0 });
}

/**
 * 比较模型当前区段（从会话记录重放，因此从不为 null）与目标区段。
 * 返回 `SystemMessage.sections` 补丁；
 * 没有变化时返回 undefined。
 */
export function diffSystemPromptSections(
	previous: Record<string, string | null>,
	current: SystemPromptSections,
): Record<string, string | null> | undefined {
	const patch: Record<string, string | null> = {};
	for (const [name, text] of Object.entries(current)) {
		if (previous[name] !== text) patch[name] = text;
	}
	for (const name of Object.keys(previous)) {
		if (current[name] === undefined) patch[name] = null;
	}
	return Object.keys(patch).length > 0 ? patch : undefined;
}
````
