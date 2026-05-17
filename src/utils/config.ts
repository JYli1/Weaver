import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { WeaverConfig, DEFAULT_CONFIG } from '../types/config';

// 配置文件路径（优先级从高到低）
function getConfigPaths(): string[] {
  return [
    join(process.cwd(), '.weaver', 'settings.json'),
    join(homedir(), '.weaver', 'settings.json'),
  ];
}

function loadJsonFile(path: string): Partial<WeaverConfig> | null {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

export function loadConfig(): WeaverConfig {
  const paths = getConfigPaths();
  let merged: Partial<WeaverConfig> = {};

  // 从低优先级到高优先级合并
  for (const path of [...paths].reverse()) {
    const cfg = loadJsonFile(path);
    if (cfg) merged = { ...merged, ...cfg };
  }

  // 环境变量覆盖
  const env = process.env;
  if (env.ANTHROPIC_API_KEY) merged.apiKey = env.ANTHROPIC_API_KEY;
  if (env.ANTHROPIC_BASE_URL) merged.baseUrl = env.ANTHROPIC_BASE_URL;
  if (env.ANTHROPIC_MODEL) merged.model = env.ANTHROPIC_MODEL;
  if (env.ANTHROPIC_CUSTOM_HEADERS) merged.customHeaders = env.ANTHROPIC_CUSTOM_HEADERS;
  if (env.API_TIMEOUT_MS) merged.timeout = parseInt(env.API_TIMEOUT_MS, 10);

  return { ...DEFAULT_CONFIG, ...merged };
}
